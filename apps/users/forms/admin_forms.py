"""Django admin forms for the custom user model.

These are the only forms in an otherwise API-only project. They are mandatory:
without a creation form that calls ``set_password``, the admin's "Add user"
page stores a **plaintext** password, and without ``ReadOnlyPasswordHashField``
the change form re-hashes the existing hash on every save.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.password_validation import validate_password

from apps.users.models import User
from apps.users.validators.user_validator import normalize_email, normalize_username


class UserAdminCreationForm(forms.ModelForm):
    """Create a user from the admin, hashing the password correctly."""

    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "username")

    def clean_password2(self) -> str:
        """Confirm the two password entries match and satisfy policy.

        Returns:
            The validated password.

        Raises:
            forms.ValidationError: If the entries differ or fail validation.
        """
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields do not match.")
        validate_password(password2)
        return password2

    def save(self, commit: bool = True) -> User:
        """Return a user with a correctly hashed password.

        Args:
            commit: Whether to persist immediately.

        Returns:
            The user instance.
        """
        user: User = super().save(commit=False)
        user.email = normalize_email(user.email)
        user.username = normalize_username(user.username)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserAdminChangeForm(forms.ModelForm):
    """Edit a user without mangling the stored password hash."""

    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text=(
            "Raw passwords are not stored, so there is no way to see this "
            "user's password. Use the change-password form instead."
        ),
    )

    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
            "groups",
            "user_permissions",
        )
