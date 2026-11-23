import tempfile
import os
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from plataforma.models import MemberProfile
from plataforma.profile_updates import save_profile


class ProfileUpdateTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        user = get_user_model().objects.create_user(username="avatar-test")
        self.profile, _ = MemberProfile.objects.get_or_create(user=user)
        self.profile.avatar.save("old.webp", SimpleUploadedFile("old.webp", b"old"))
        self.old = self.profile.avatar.name
        self.storage = self.profile.avatar.storage

    def form(self, remove=False):
        return SimpleNamespace(save=Mock(), cleaned_data={
            "remover_avatar": remove,
            "avatar": SimpleUploadedFile("new.webp", b"new"),
        })

    def test_old_file_deleted_only_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            updated = save_profile(self.form(), self.profile.pk)
            self.assertTrue(self.storage.exists(self.old))
            self.assertTrue(self.storage.exists(updated.avatar.name))
        self.assertFalse(self.storage.exists(self.old))

    def test_upload_failure_preserves_previous_reference(self):
        with patch.object(self.storage, "save", side_effect=OSError("storage unavailable")):
            with self.assertRaises(OSError):
                save_profile(self.form(), self.profile.pk)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar.name, self.old)
        self.assertTrue(self.storage.exists(self.old))

    def test_database_failure_removes_new_file_and_keeps_old(self):
        with patch.object(MemberProfile, "save", side_effect=DatabaseError("write failed")):
            with self.assertRaises(DatabaseError):
                save_profile(self.form(), self.profile.pk)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar.name, self.old)
        self.assertEqual(self.storage.listdir("avatars")[1], [self.old.split("/")[-1]])

    def test_cleanup_failure_does_not_undo_update(self):
        with patch.object(self.storage, "delete", side_effect=OSError("delete failed")):
            with self.assertLogs("plataforma.profile_updates", level="WARNING"):
                with self.captureOnCommitCallbacks(execute=True):
                    updated = save_profile(self.form(), self.profile.pk)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar.name, updated.avatar.name)
        self.assertTrue(self.storage.exists(self.old))

    def test_explicit_removal_waits_for_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            save_profile(self.form(remove=True), self.profile.pk)
            self.assertTrue(self.storage.exists(self.old))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.avatar)
        self.assertFalse(self.storage.exists(self.old))

    def test_cleanup_only_removes_old_unreferenced_files_with_explicit_flag(self):
        orphan = self.storage.save("avatars/orphan.webp", SimpleUploadedFile("orphan.webp", b"old"))
        recent = self.storage.save("avatars/recent.webp", SimpleUploadedFile("recent.webp", b"new"))
        old_time = (timezone.now() - timedelta(days=2)).timestamp()
        os.utime(self.storage.path(orphan), (old_time, old_time))
        os.utime(self.storage.path(self.old), (old_time, old_time))
        call_command("limpar_avatars_orfaos", stdout=StringIO())
        self.assertTrue(self.storage.exists(orphan))
        call_command("limpar_avatars_orfaos", aplicar=True, stdout=StringIO())
        self.assertFalse(self.storage.exists(orphan))
        self.assertTrue(self.storage.exists(recent))
        self.assertTrue(self.storage.exists(self.old))

    def test_nested_transaction_rejected_before_upload(self):
        with transaction.atomic():
            with self.assertRaises(RuntimeError):
                save_profile(self.form(), self.profile.pk)
        self.assertEqual(self.storage.listdir("avatars")[1], [self.old.split("/")[-1]])


@skipUnless(connection.vendor == "postgresql", "Concorrência exige PostgreSQL")
class ConcurrentProfileUpdateTests(TransactionTestCase):
    def test_concurrent_uploads_keep_only_current_file(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            user = get_user_model().objects.create_user(username="concurrent-avatar")
            profile, _ = MemberProfile.objects.get_or_create(user=user)
            profile.avatar.save("old.webp", SimpleUploadedFile("old.webp", b"old"))
            profile_id = profile.pk
            barrier = Barrier(2)

            def update(number):
                close_old_connections()
                try:
                    form = SimpleNamespace(save=Mock(), cleaned_data={
                        "avatar": SimpleUploadedFile(f"upload-{number}.webp", b"new"),
                    })
                    barrier.wait(timeout=10)
                    return save_profile(form, profile_id).avatar.name
                finally:
                    close_old_connections()

            with ThreadPoolExecutor(max_workers=2) as executor:
                names = list(executor.map(update, range(2)))
            profile.refresh_from_db()
            self.assertIn(profile.avatar.name, names)
            self.assertTrue(profile.avatar.storage.exists(profile.avatar.name))
            self.assertEqual(profile.avatar.storage.listdir("avatars")[1],
                             [profile.avatar.name.split("/")[-1]])
