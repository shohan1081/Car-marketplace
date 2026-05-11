"""
Custom User Manager for creating users and superusers
"""

from django.contrib.auth.models import BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifier
    instead of username for authentication.
    """
    
    def create_user(self, email, password=None, name=None, username=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        The name and username fields are now optional.
        
        Args:
            email (str): User's email address
            password (str): User's password
            name (str, optional): User's full name. Defaults to None.
            username (str, optional): User's unique username. Defaults to None.
            **extra_fields: Additional fields for user model
            
        Returns:
            User: Created user instance
            
        Raises:
            ValueError: If email is not provided
        """
        if not email:
            raise ValueError(_('The Email field must be set'))
        
        # Normalize email (lowercase domain part)
        email = self.normalize_email(email)
        
        if name is None:
            name = email.split('@')[0] # Default to email local part

        if username is None:
            username = email.split('@')[0].lower() # Default to email local part, lowercase
        
        # Set default values
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_email_verified', False)
        
        # Create user instance
        user = self.model(
            email=email,
            name=name,
            username=username,
            **extra_fields
        )
        
        # Set password (this will hash the password)
        if password:
            user.set_password(password)
        
        # Save to database
        user.save(using=self._db)
        
        return user
    
    def create_superuser(self, email, password=None, name=None, username=None, **extra_fields):
        """
        Create and save a superuser with the given email, password, name, and username.
        
        Args:
            email (str): Superuser's email address
            password (str): Superuser's password
            name (str, optional): Superuser's full name. Defaults to None.
            username (str, optional): Superuser's unique username. Defaults to None.
            **extra_fields: Additional fields for user model
            
        Returns:
            User: Created superuser instance
            
        Raises:
            ValueError: If is_staff or is_superuser is not True
        """
        # Set superuser flags
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_email_verified', True)  # Auto-verify superuser email
        
        # Validate flags
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        # Default name and username if not provided
        if name is None:
            name = email.split('@')[0]
        if username is None:
            username = email.split('@')[0].lower()

        # Create superuser using create_user method
        return self.create_user(email, password=password, name=name, username=username, **extra_fields)
    
    def create_firebase_user(self, email, firebase_uid, name=None, username=None, auth_provider='google', **extra_fields):
        """
        Create user from Firebase authentication (Google, Apple, etc.)
        
        Args:
            email (str): User's email from Firebase
            firebase_uid (str): Firebase UID
            name (str, optional): User's name from Firebase. Defaults to None.
            username (str, optional): User's username from Firebase. Defaults to None.
            auth_provider (str): Authentication provider (google, apple)
            **extra_fields: Additional fields
            
        Returns:
            User: Created or existing user instance
        """
        # Check if user already exists with this email
        try:
            user = self.get(email=email)
            
            # Update Firebase UID if not set
            if not user.firebase_uid:
                user.firebase_uid = firebase_uid
                user.auth_provider = auth_provider
                user.is_email_verified = True  # Firebase emails are pre-verified
                user.save()
            
            return user
            
        except self.model.DoesNotExist:
                        
                        # Create new user
                        extra_fields.setdefault('firebase_uid', firebase_uid)
                        extra_fields.setdefault('auth_provider', auth_provider)
                        extra_fields.setdefault('is_email_verified', True)
                        extra_fields.setdefault('is_active', True)
                        
                        # Default name and username if not provided
                        if name is None:
                            name = email.split('@')[0]
                        if username is None:
                            username = email.split('@')[0].lower()
            
                        # No password needed for Firebase users
                        return self.create_user(email, password=None, name=name, username=username, **extra_fields)