document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("premiumForm");
    const submitBtn = document.getElementById("premiumSubmitBtn");

    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            const emailInput = document.getElementById("email");
            const email = emailInput.value.trim();

            if (!email) {
                alert("Please enter a valid email address.");
                return;
            }

            // Loading state
            submitBtn.disabled = true;
            submitBtn.textContent = "Redirecting to Stripe...";
            submitBtn.style.opacity = "0.7";

            try {
                const response = await fetch("/create-premium-checkout", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ email: email }),
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.url) {
                        window.location.href = data.url;
                    } else {
                        throw new Error("No checkout URL returned.");
                    }
                } else {
                    throw new Error("Failed to initiate checkout.");
                }

            } catch (error) {
                console.error("Checkout Error:", error);
                alert("Something went wrong initializing checkout. Please try again.");

                // Reset button
                submitBtn.disabled = false;
                submitBtn.textContent = "Proceed to Checkout";
                submitBtn.style.opacity = "1";
            }
        });
    }
});
