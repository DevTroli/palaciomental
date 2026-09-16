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


        document
            .getElementById("waitlistForm")
            .addEventListener("submit", function(event) {

                event.preventDefault();

                showConfirmation(this);

            });


        document
            .getElementById("waitlistFormBottom")
            .addEventListener("submit", function(event) {

                event.preventDefault();

                showConfirmation(this);

            });
