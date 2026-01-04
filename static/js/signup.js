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
      if (plan === 'premium') {
        // Premium: No Email (Stripe collects it), Tag as premium
        selectedPlanInput.value = 'premium';
        emailGroup.classList.add("hidden");
        emailInput.removeAttribute("required");

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
      authSection.style.display = "block";
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

  // 3. Profession "Other" Toggle
  if (professionSelect) {
    professionSelect.addEventListener("change", () => {
      if (professionSelect.value === "other") {
        otherProfessionGroup.classList.remove("hidden");
        otherProfessionInput.setAttribute("required", "true");
      } else {
        otherProfessionGroup.classList.add("hidden");
        otherProfessionInput.removeAttribute("required");
      }
    });
  }

  // 4. Form Submit Cleanup
  const form = document.querySelector("form");
  if (form) {
    form.addEventListener("submit", (e) => {
      // If "Other" is selected, copy value to select for backend consistency if needed
      // actually backend usually takes the select value. If it's "other", backend sees "other".
      // App.py: profession = request.form.get("profession", "")
      // It doesn't seem to look for "other_profession". 
      // Let's check app.py logic logic for profession again or just append it.
      // Looking at app.py, it just grabs "profession".
      // So if value is "other", we might want to put the custom text into the 'profession' field before submit?
      // Or maybe the backend handles 'other'? 
      // The current app.py just saves `profession`. If I send "other", it saves "other".
      // Let's swap the values just in case the user wants the specific text.

      if (professionSelect.value === "other" && otherProfessionInput.value.trim() !== "") {
        // Create a hidden input or change option value? 
        // Simplest: change the selected option's value
        const selectedOption = professionSelect.options[professionSelect.selectedIndex];
        selectedOption.value = otherProfessionInput.value.trim();
      }
    });
  }
});
