"""
AWS Profile Manager

Manages AWS sessions using default credentials from PowerShell script.
All operations use the default AWS profile with credentials stored via PowerShell.
"""

import logging
import boto3
from typing import Optional, Dict
from botocore.exceptions import ClientError, NoCredentialsError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AWSProfileManager:
    """Manages AWS sessions using default credentials"""

    # Profile purposes (kept for backward compatibility)
    LAMBDA_PROFILE = "default"
    DATA_PROFILE = "default"
    DEFAULT_PROFILE = "default"

    def __init__(self):
        """Initialize the profile manager with default session"""
        self.sessions: Dict[str, boto3.Session] = {}
        self.credentials: Dict[str, object] = {}
        self._initialize_profiles()

    def _initialize_profiles(self):
        """Initialize AWS default session"""
        # All profiles use default session (credentials from PowerShell)
        try:
            default_session = boto3.Session()
            default_credentials = default_session.get_credentials()

            # Store same session for all profile types
            self.sessions[self.DEFAULT_PROFILE] = default_session
            self.sessions[self.LAMBDA_PROFILE] = default_session
            self.sessions[self.DATA_PROFILE] = default_session

            self.credentials[self.DEFAULT_PROFILE] = default_credentials
            self.credentials[self.LAMBDA_PROFILE] = default_credentials
            self.credentials[self.DATA_PROFILE] = default_credentials

            logger.info("Initialized AWS session using default credentials")
        except Exception as e:
            logger.error(f"Failed to initialize AWS session: {e}")
            logger.error("Ensure AWS credentials are configured via PowerShell script")

    def get_session(self, purpose: str = DEFAULT_PROFILE) -> Optional[boto3.Session]:
        """
        Get a boto3 session for a specific purpose

        Args:
            purpose: One of LAMBDA_PROFILE, DATA_PROFILE, or DEFAULT_PROFILE

        Returns:
            boto3.Session object or None if not available
        """
        session = self.sessions.get(purpose)
        if session is None:
            logger.warning(f"Profile '{purpose}' not available, falling back to default")
            session = self.sessions.get(self.DEFAULT_PROFILE)
        return session

    def get_credentials(self, purpose: str = DEFAULT_PROFILE):
        """
        Get AWS credentials for a specific purpose with automatic refresh

        Args:
            purpose: One of LAMBDA_PROFILE, DATA_PROFILE, or DEFAULT_PROFILE

        Returns:
            Credentials object or None if not available
        """
        # Refresh credentials if expired
        self._refresh_credentials_if_needed(purpose)

        credentials = self.credentials.get(purpose)
        if credentials is None:
            logger.warning(f"Credentials for '{purpose}' not available, falling back to default")
            self._refresh_credentials_if_needed(self.DEFAULT_PROFILE)
            credentials = self.credentials.get(self.DEFAULT_PROFILE)
        return credentials

    def _refresh_credentials_if_needed(self, purpose: str):
        """
        Refresh credentials if they are expired or about to expire

        Args:
            purpose: Profile purpose to check
        """
        try:
            session = self.sessions.get(purpose)
            if not session:
                return

            # Get fresh credentials
            credentials = session.get_credentials()

            # Check if credentials are still valid
            if credentials:
                # Refresh frozen credentials
                frozen_creds = credentials.get_frozen_credentials()
                if frozen_creds:
                    self.credentials[purpose] = credentials
                    logger.debug(f"Refreshed credentials for {purpose}")
            else:
                logger.warning(f"Unable to get credentials for {purpose}")

        except Exception as e:
            logger.warning(f"Error refreshing credentials for {purpose}: {e}")

    def validate_credentials(self, purpose: str = DATA_PROFILE) -> bool:
        """
        Validate that credentials are working by making a test API call

        Args:
            purpose: Profile purpose to validate

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            session = self.get_session(purpose)
            if not session:
                return False

            # Make a simple STS call to verify credentials
            sts = session.client('sts')
            response = sts.get_caller_identity()

            logger.info(f"✓ Credentials valid for {purpose}")
            logger.info(f"  Account: {response.get('Account')}")
            logger.info(f"  User: {response.get('Arn')}")
            return True

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'ExpiredToken':
                logger.error(f"✗ AWS credentials expired")
                logger.error(f"  Please refresh credentials using PowerShell script")
            else:
                logger.error(f"✗ AWS credentials invalid: {e}")
            return False

        except Exception as e:
            logger.error(f"✗ Error validating AWS credentials: {e}")
            return False

    def _get_profile_name(self, purpose: str) -> str:
        """Get the actual profile name (always default)"""
        return 'default'

    def create_client(self, service_name: str, region_name: str = None,
                     purpose: str = DATA_PROFILE, **kwargs):
        """
        Create a boto3 client with the appropriate profile

        Args:
            service_name: AWS service name (e.g., 'rds', 'cloudwatch', 'logs')
            region_name: AWS region name
            purpose: Profile purpose (LAMBDA_PROFILE or DATA_PROFILE)
            **kwargs: Additional arguments for boto3 client

        Returns:
            Boto3 client object
        """
        session = self.get_session(purpose)
        if session is None:
            raise NoCredentialsError(f"No credentials available for purpose: {purpose}")

        client_kwargs = kwargs.copy()
        if region_name:
            client_kwargs['region_name'] = region_name

        try:
            return session.client(service_name, **client_kwargs)
        except Exception as e:
            logger.error(f"Failed to create {service_name} client: {e}")
            raise

    def get_caller_identity(self, purpose: str = DEFAULT_PROFILE) -> Optional[Dict]:
        """
        Get AWS account information for a profile

        Args:
            purpose: Profile purpose

        Returns:
            Dictionary with Account, UserId, and Arn information
        """
        try:
            session = self.get_session(purpose)
            if session is None:
                return None

            sts = session.client('sts')
            identity = sts.get_caller_identity()
            return {
                'Account': identity.get('Account'),
                'UserId': identity.get('UserId'),
                'Arn': identity.get('Arn')
            }
        except Exception as e:
            logger.error(f"Failed to get caller identity for '{purpose}': {e}")
            return None

    def validate_profiles(self) -> Dict[str, bool]:
        """
        Validate all configured profiles

        Returns:
            Dictionary mapping profile purposes to validity status
        """
        results = {}

        for purpose in [self.LAMBDA_PROFILE, self.DATA_PROFILE, self.DEFAULT_PROFILE]:
            identity = self.get_caller_identity(purpose)
            results[purpose] = identity is not None

            if identity:
                logger.info(f"✓ Profile '{purpose}' valid - Account: {identity['Account']}")
            else:
                logger.warning(f"✗ Profile '{purpose}' invalid or not configured")

        return results


# Global instance for convenience
_profile_manager = None


def get_profile_manager() -> AWSProfileManager:
    """Get the global AWS profile manager instance"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = AWSProfileManager()
    return _profile_manager


# Convenience functions for backward compatibility
def get_lambda_session() -> boto3.Session:
    """Get session for Lambda endpoint access"""
    return get_profile_manager().get_session(AWSProfileManager.LAMBDA_PROFILE)


def get_data_session() -> boto3.Session:
    """Get session for production data access"""
    return get_profile_manager().get_session(AWSProfileManager.DATA_PROFILE)


def get_lambda_credentials():
    """Get credentials for Lambda endpoint access"""
    return get_profile_manager().get_credentials(AWSProfileManager.LAMBDA_PROFILE)


def get_data_credentials():
    """Get credentials for production data access"""
    return get_profile_manager().get_credentials(AWSProfileManager.DATA_PROFILE)

