// Antigravity Signup Logic
// Handles plan selection, transitions, and form validation toggling.

document.addEventListener("DOMContentLoaded", () => {
  const planSelection = document.getElementById("planSelection");
  const authSection = document.getElementById("authSection");
  const emailGroup = document.getElementById("emailGroup");
  const emailInput = document.getElementById("email");
  const selectedPlanInput = document.getElementById("selectedPlanInput");
  const promoCodeContainer = document.getElementById("promoCodeContainer");
  const formTitle = document.getElementById("formTitle");
  const formSubtitle = document.getElementById("formSubtitle");
  const submitBtn = document.getElementById("submitBtn");

  // Profession Selectors
  const professionSelect = document.getElementById("profession");
  const otherProfessionGroup = document.getElementById("otherProfessionGroup");
  const otherProfessionInput = document.getElementById("other_profession");

  // 1. Plan Selection Logic
  window.selectPlan = (plan) => {
    // Fade out plan selection
    planSelection.classList.remove("fade-in");
    planSelection.classList.add("fade-out");

    setTimeout(() => {
      planSelection.classList.add("hidden");

      // Configure Form based on plan
      // Configure Form based on plan
      if (plan === 'premium') {
        // Premium: Email IS required now (passed to Stripe)
        selectedPlanInput.value = 'premium';
        // Ensure email is visible & required
        emailGroup.classList.remove("hidden");
        emailInput.setAttribute("required", "true");

        formTitle.textContent = "Setup Premium Profile";
        formSubtitle.textContent = "Enter your details to proceed to secure checkout.";
        submitBtn.textContent = "Proceed to Payment";

        // Show Promo Code for Premium
        if (promoCodeContainer) promoCodeContainer.classList.remove("hidden");

      } else {
        // Free: Email Required
        selectedPlanInput.value = 'free';
        emailGroup.classList.remove("hidden");
        emailInput.setAttribute("required", "true");

        formTitle.textContent = "Create Free Account";
        formSubtitle.textContent = "Join thousands of pros growing their business.";
        submitBtn.textContent = "Create Account";

        // Hide Promo Code for Free
        if (promoCodeContainer) promoCodeContainer.classList.add("hidden");
      }

      // Fade in auth section
      authSection.classList.remove("hidden");
      // Trigger reflow
      void authSection.offsetWidth;
      authSection.classList.add("fade-in");
      authSection.style.opacity = "1";
      // FIX: Use flex to maintain centering defined in CSS
      authSection.style.display = "flex";

      // Scroll to form (smoothly)
      setTimeout(() => {
        authSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }, 500);
  };

  // 2. Back to Plans Logic
  window.showPlans = () => {
    authSection.classList.remove("fade-in");
    authSection.classList.add("fade-out"); // We'd need to define this style reverse or just hide

    // Simple transition back
    authSection.style.opacity = "0";

    setTimeout(() => {
      authSection.classList.add("hidden");
      authSection.style.display = "none";
      authSection.classList.remove("fade-out");

      planSelection.classList.remove("hidden");
      planSelection.classList.remove("fade-out");
      void planSelection.offsetWidth;
      planSelection.classList.add("fade-in");
    }, 500);
  };

  // 4. Form Submit Cleanup
  const form = document.querySelector("form");
  if (form) {
    form.addEventListener("submit", (e) => {
      // Standard submit
    });
  }
});
