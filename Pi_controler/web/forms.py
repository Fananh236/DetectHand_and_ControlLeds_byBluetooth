"""First-run account setup form."""

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class InitialSetupForm(UserCreationForm):
    """Create the one local administrator on a fresh installation."""

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = True
        if commit:
            user.save()
        return user
