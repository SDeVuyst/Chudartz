from django.core.exceptions import ValidationError

def validate_image_max_size(image):
    max_size_kb = 300
    if image.size > max_size_kb * 1024:
        raise ValidationError(f"De afbeelding mag niet groter zijn dan {max_size_kb}KB.")