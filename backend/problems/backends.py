from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailOrUsernameBackend(ModelBackend):
    """Allow login with either username or email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        # Try exact username first
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Fall back to email lookup
            try:
                user = User.objects.get(email__iexact=username)
            except User.MultipleObjectsReturned:
                # More than one account with that email — refuse (ambiguous)
                return None
            except User.DoesNotExist:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
