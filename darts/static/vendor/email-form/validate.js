// contact.js
document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('email-form'); // Use id to select the form
  const loadingMessage = document.querySelector('.loading');
  const errorMessage = document.querySelector('.error-message');
  const sentMessage = document.querySelector('.sent-message');

  form.addEventListener('submit', function(event) {
      console.log("submit");
      event.preventDefault(); // Prevent the default form submission

      // Show loading message and hide other messages
      loadingMessage.style.display = 'block';
      errorMessage.style.display = 'none';
      sentMessage.style.display = 'none';

      // Create FormData object from the form
      const formData = new FormData(form);

      fetch('/contact', {
          method: 'POST',
          body: formData,
          headers: {
              'X-Requested-With': 'XMLHttpRequest', // Indicate AJAX request
              'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value // CSRF Token
          }
      })
      .then(response => response.json())
      .then(data => {
          loadingMessage.style.display = 'none';
          if (data.success) {
              sentMessage.style.display = 'block';
              form.reset(); // Optionally reset the form fields
          } else {
              errorMessage.textContent = data.error || 'Er is iets misgegaan. Probeer binnen een paar minuten opnieuw.';
              errorMessage.style.display = 'block';
          }
      })
      .catch(() => {
          loadingMessage.style.display = 'none';
          errorMessage.textContent = 'Er is iets misgegaan. Probeer binnen een paar minuten opnieuw.';
          errorMessage.style.display = 'block';
      });
  });
});
