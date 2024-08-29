document.addEventListener('DOMContentLoaded', function() {
    var languageLinks = document.querySelectorAll('.language-switcher');

    languageLinks.forEach(function(link) {
        link.addEventListener('click', function(event) {
            event.preventDefault(); // Prevent the default anchor behavior

            var languageCode = this.getAttribute('data-language');
            var form = document.getElementById('language-form');
            form.querySelector('input[name="language"]').value = languageCode;

            form.submit(); // Submit the form
        });
    });
});
