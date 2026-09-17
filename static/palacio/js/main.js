function showConfirmation(form) {

            const waitBox = form.closest(".wait-box");

            if (waitBox) {

                const formState =
                    waitBox.querySelector("#formState");

                const confirmation =
                    waitBox.querySelector("#confirmation");

                formState.style.display = "none";
                confirmation.classList.add("active");

            } else {

                form.innerHTML = `
                    <div style="
                        width:100%;
                        padding:15px;
                        text-align:center;
                        color:#45694C;
                        font-family:Arial,sans-serif;
                        font-size:14px;
                        font-weight:600;
                    ">
                        ✓ Você está na lista!
                    </div>
                `;

            }

        }


        /* =====================================================
           MÁSCARA DE TELEFONE — (DD) 00000-0000
           Aceita só dígitos e formata enquanto digita.
        ====================================================== */

        function maskPhone(value) {

            const digits = value.replace(/\D/g, "").slice(0, 11);

            if (digits.length === 0) {
                return "";
            }

            if (digits.length === 1) {
                return "(" + digits;
            }

            // A partir de 2 dígitos o DDD fecha sozinho: "(11) "
            const ddd = digits.slice(0, 2);
            const rest = digits.slice(2);

            let out = "(" + ddd + ") ";

            if (rest.length <= 5) {
                return out + rest;
            }

            // A partir do 6º dígito o hífen entra sozinho
            return out + rest.slice(0, 5) + "-" + rest.slice(5);

        }


        ["telefone", "telefoneBottom"].forEach(function(id) {

            const input = document.getElementById(id);

            if (!input) {
                return;
            }

            input.addEventListener("input", function() {
                this.value = maskPhone(this.value);
            });

            // Campo só para números: bloqueia letras e símbolos na digitação.
            // (Parênteses, espaço e hífen são colocados sozinhos pela máscara.)
            input.addEventListener("keydown", function(event) {

                const navKeys = [
                    "Backspace", "Delete", "Tab",
                    "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
                    "Home", "End"
                ];

                if (navKeys.includes(event.key)) {
                    return;
                }

                if ((event.ctrlKey || event.metaKey) &&
                    ["a", "c", "v", "x", "z"].includes(event.key.toLowerCase())) {
                    return;
                }

                if (!/^\d$/.test(event.key)) {
                    event.preventDefault();
                }

            });

        });


        /* =====================================================
           POPUP DE REGISTRO + TRAVA DA SESSÃO
        ====================================================== */

        const REGISTER_KEY = "pm_registered";


        /* Trava por cookie: cadastrado uma vez, o formulário fica
           em "Você está na lista!". Apagando o cookie dá para
           cadastrar outra conta. */
        function setCookie(name, value, days) {

            let expires = "";

            if (days) {
                const date = new Date();
                date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
                expires = "; expires=" + date.toUTCString();
            }

            document.cookie =
                name + "=" + encodeURIComponent(value) + expires +
                "; path=/; SameSite=Lax";

        }


        function getCookie(name) {

            const cookies = document.cookie ? document.cookie.split("; ") : [];

            for (let i = 0; i < cookies.length; i++) {
                const parts = cookies[i].split("=");
                if (parts[0] === name) {
                    return decodeURIComponent(parts.slice(1).join("="));
                }
            }

            return null;

        }

        const popupOverlay = document.getElementById("popupOverlay");
        const popupClose = document.getElementById("popupClose");

        // Enquanto true, os confetes continuam caindo.
        let partyRunning = false;


        function openPopup() {

            if (!popupOverlay) {
                return;
            }

            popupOverlay.classList.add("active");
            popupOverlay.setAttribute("aria-hidden", "false");
            document.body.style.overflow = "hidden";

            partyRunning = true;
            celebrate();

        }


        function closePopup() {

            // Para de emitir confetes; os que estão no ar
            // terminam de cair e o canvas limpa sozinho.
            partyRunning = false;

            if (!popupOverlay) {
                return;
            }

            popupOverlay.classList.remove("active");
            popupOverlay.setAttribute("aria-hidden", "true");
            document.body.style.overflow = "";

        }


        if (popupClose) {
            popupClose.addEventListener("click", closePopup);
        }

        if (popupOverlay) {
            popupOverlay.addEventListener("click", function(event) {
                if (event.target === popupOverlay) {
                    closePopup();
                }
            });
        }

        document.addEventListener("keydown", function(event) {
            if (event.key === "Escape") {
                closePopup();
            }
        });


        /* =====================================================
           FESTA — confetes verdes e roxos em canvas
        ====================================================== */

        function celebrate() {

            const canvas = document.getElementById("partyCanvas");

            if (!canvas) {
                return;
            }

            const ctx = canvas.getContext("2d");

            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            canvas.classList.add("active");

            // Paleta da marca: roxos + verdes
            const COLORS = [
                "#542C72", "#765491", "#B388FF", "#321943",
                "#6C9B73", "#45694C", "#9CCC9C", "#E4EEE5"
            ];

            const pieces = [];


            function burst(x, y, count) {

                for (let i = 0; i < count; i++) {

                    const angle = Math.random() * Math.PI * 2;
                    const speed = 4 + Math.random() * 9;

                    pieces.push({
                        x: x,
                        y: y,
                        vx: Math.cos(angle) * speed,
                        vy: Math.sin(angle) * speed - 6,
                        w: 6 + Math.random() * 7,
                        h: 8 + Math.random() * 8,
                        rotation: Math.random() * Math.PI * 2,
                        vr: (Math.random() - 0.5) * 0.3,
                        sway: Math.random() * Math.PI * 2,
                        color: COLORS[Math.floor(Math.random() * COLORS.length)],
                        life: 1
                    });

                }

            }


            // Pontos de explosão em rodízio: centro e laterais
            const spots = [
                [0.5, 0.7],
                [0.2, 0.65],
                [0.8, 0.65]
            ];
            let spot = 0;
            let frames = 0;

            // Primeira explosão imediata
            burst(canvas.width / 2, canvas.height * 0.7, 90);

            function tick() {

                frames++;

                // Enquanto o popup estiver aberto, nova explosão
                // a cada ~0,75s: confetes infinitos até Continuar.
                if (partyRunning && frames % 45 === 0) {
                    const s = spots[spot % spots.length];
                    spot++;
                    burst(canvas.width * s[0], canvas.height * s[1], 45);
                }

                ctx.clearRect(0, 0, canvas.width, canvas.height);

                pieces.forEach(function(p) {

                    if (p.life <= 0) {
                        return;
                    }

                    p.vy += 0.28;
                    p.vx *= 0.99;
                    p.sway += 0.05;

                    p.x += p.vx + Math.sin(p.sway) * 1.2;
                    p.y += p.vy;
                    p.rotation += p.vr;

                    if (p.y > canvas.height + 30) {
                        p.life = 0;
                        return;
                    }

                    p.life -= 0.004;

                    ctx.save();
                    ctx.translate(p.x, p.y);
                    ctx.rotate(p.rotation);
                    ctx.globalAlpha = Math.min(1, Math.max(p.life * 1.5, 0));
                    ctx.fillStyle = p.color;
                    ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
                    ctx.restore();

                });

                const alive = pieces.some(function(p) { return p.life > 0; });

                if (partyRunning || alive) {
                    requestAnimationFrame(tick);
                } else {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    canvas.classList.remove("active");
                }

            }

            requestAnimationFrame(tick);

        }


        ["waitlistForm", "waitlistFormBottom"].forEach(function(id) {

            const form = document.getElementById(id);

            if (!form) {
                return;
            }

            // Cookie de cadastro ativo: mantém o formulário travado
            // em "Você está na lista!" sem abrir o popup de novo.
            // Apagando o cookie, libera para cadastrar outra conta.
            if (getCookie(REGISTER_KEY) === "1") {
                showConfirmation(form);
            }

            form.addEventListener("submit", function(event) {

                event.preventDefault();

                showConfirmation(this);

                setCookie(REGISTER_KEY, "1", 365);

                openPopup();

            });

        });
