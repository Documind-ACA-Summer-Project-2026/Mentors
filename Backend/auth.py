import datetime
import os
import bcrypt
import jwt
import psycopg2
import psycopg2.extras
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from google.oauth2 import id_token
from google.auth.transport import requests
from google.auth.exceptions import GoogleAuthError

from config import JWT_SECRET, ALGORITHM
from database import get_db_connection
from schemas import SignupRequest, SigninRequest, GoogleAuthRequest, VerifyOtpRequest, ResendOtpRequest, ForgotPasswordRequest, ResetPasswordRequest
from email_utils import send_otp_email
from error_handlers import (
    AuthenticationError, ValidationError, ResourceNotFoundError,
    DatabaseError, ExternalServiceError, handle_database_error,
    handle_google_auth_error, log_error
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# JWT Helpers
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

# Auth dependency
def get_current_user(request: Request):
    """Verify and return current authenticated user from token."""
    try:
        token = request.cookies.get("access_token")
        if not token:
            raise AuthenticationError("No authentication token found")
        
        payload = decode_token(token)
        if not payload:
            raise AuthenticationError("Invalid or expired token")
        
        # Verify user exists in the database
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id, name, email FROM users WHERE id = %s", (payload.get("id"),))
                    row = cursor.fetchone()
                    if not row:
                        raise AuthenticationError("User session is invalid. Please sign in again.")
                    return {"id": row[0], "name": row[1], "email": row[2]}
        except AuthenticationError:
            raise
        except psycopg2.Error as e:
            log_error(e, "get_current_user database validation")
            raise handle_database_error(e)
        except Exception as e:
            log_error(e, "get_current_user")
            raise DatabaseError("Failed to validate user session")
    except Exception as e:
        log_error(e, "get_current_user")
        raise

# Password utils
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Endpoints
@router.post("/signup")
def signup(req: SignupRequest, response: Response):
    """Register a new user with email verification."""
    try:
        # Validate input
        if not req.email or "@" not in req.email:
            raise ValidationError("Invalid email format", "email")
        if not req.password or len(req.password) < 6:
            raise ValidationError("Password must be at least 6 characters", "password")
        if not req.name or len(req.name.strip()) == 0:
            raise ValidationError("Name is required", "name")
        
        import random
        hashed = hash_password(req.password)
        otp_code = f"{random.randint(100000, 999999)}"
        otp_expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    # Check if email is already registered
                    cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (req.email,))
                    existing_user = cursor.fetchone()
                    
                    if existing_user:
                        if existing_user["is_verified"]:
                            raise ValidationError("Email already registered", "email")
                        else:
                            # User exists but is unverified. Overwrite details and send new OTP.
                            cursor.execute(
                                "UPDATE users SET name = %s, password_hash = %s, otp_code = %s, otp_expires_at = %s WHERE id = %s RETURNING id",
                                (req.name, hashed, otp_code, otp_expires_at, existing_user["id"])
                            )
                            user_id = cursor.fetchone()[0]
                    else:
                        # New user signup
                        cursor.execute(
                            "INSERT INTO users (name, email, password_hash, is_verified, otp_code, otp_expires_at) VALUES (%s, %s, %s, FALSE, %s, %s) RETURNING id",
                            (req.name, req.email, hashed, otp_code, otp_expires_at)
                        )
                        user_id = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"New signup attempt for email: {req.email}")
        except psycopg2.errors.UniqueViolation:
            raise ValidationError("Email already registered", "email")
        except psycopg2.Error as e:
            log_error(e, "signup database")
            raise handle_database_error(e)
        
        # Send verification email (falls back to console printing if SMTP is not configured)
        try:
            send_otp_email(req.email, otp_code)
        except Exception as e:
            log_error(e, "signup email sending")
            logger.warning(f"Failed to send OTP email to {req.email}, but user was created")
            # Don't fail the signup if email fails - user can still proceed
        
        return {"status": "verification_required", "email": req.email}
    
    except ValidationError as ve:
        raise
    except Exception as e:
        log_error(e, "signup")
        raise DatabaseError("Signup failed. Please try again.")

@router.post("/verify-otp")
def verify_otp(req: VerifyOtpRequest, response: Response):
    """Verify OTP and complete email verification."""
    try:
        # Validate input
        if not req.email or "@" not in req.email:
            raise ValidationError("Invalid email format", "email")
        if not req.otp or len(req.otp) != 6 or not req.otp.isdigit():
            raise ValidationError("OTP must be a 6-digit number", "otp")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute(
                        "SELECT id, name, email, otp_code, otp_expires_at FROM users WHERE email = %s",
                        (req.email,)
                    )
                    user = cursor.fetchone()
                    
                    if not user:
                        raise ResourceNotFoundError("User", req.email)
                    
                    if not user["otp_code"] or not user["otp_expires_at"]:
                        raise ValidationError("No OTP code requested for this email")
                    
                    if user["otp_code"] != req.otp:
                        raise ValidationError("Invalid verification code", "otp")
                    
                    # Check expiration
                    now = datetime.datetime.utcnow()
                    if user["otp_expires_at"] < now:
                        raise ValidationError("Verification code has expired", "otp")
                    
                    # Update user as verified
                    cursor.execute(
                        "UPDATE users SET is_verified = TRUE, otp_code = NULL, otp_expires_at = NULL WHERE id = %s",
                        (user["id"],)
                    )
                    conn.commit()
                    
                    user_data = {"id": user["id"], "email": user["email"], "name": user["name"]}
                    logger.info(f"Email verification successful for: {req.email}")
        except psycopg2.Error as e:
            log_error(e, "verify_otp database")
            raise handle_database_error(e)
        
        token = create_access_token(user_data)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            max_age=7 * 24 * 3600,
            samesite="lax",
            secure=False,
            path="/"
        )
        return {"user": user_data}
    
    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        log_error(e, "verify_otp")
        raise DatabaseError("OTP verification failed")

@router.post("/resend-otp")
def resend_otp(req: ResendOtpRequest):
    """Resend OTP verification code."""
    try:
        # Validate input
        if not req.email or "@" not in req.email:
            raise ValidationError("Invalid email format", "email")
        
        import random
        otp_code = f"{random.randint(100000, 999999)}"
        otp_expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (req.email,))
                    user = cursor.fetchone()
                    
                    if not user:
                        raise ResourceNotFoundError("User", req.email)
                    
                    if user["is_verified"]:
                        return {"status": "already_verified", "message": "Email is already verified"}
                    
                    cursor.execute(
                        "UPDATE users SET otp_code = %s, otp_expires_at = %s WHERE id = %s",
                        (otp_code, otp_expires_at, user["id"])
                    )
                    conn.commit()
                    logger.info(f"OTP resent for email: {req.email}")
        except psycopg2.Error as e:
            log_error(e, "resend_otp database")
            raise handle_database_error(e)
        
        # Send verification email
        try:
            send_otp_email(req.email, otp_code)
        except Exception as e:
            log_error(e, "resend_otp email sending")
            logger.warning(f"Failed to send OTP email to {req.email}")
            # Don't fail the API call if email fails
        
        return {"status": "success", "message": "Verification code resent successfully"}
    
    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        log_error(e, "resend_otp")
        raise DatabaseError("Failed to resend verification code")

@router.post("/signin")
def signin(req: SigninRequest, response: Response):
    """Sign in user with email and password."""
    try:
        # Validate input
        if not req.email or "@" not in req.email:
            raise ValidationError("Invalid email format", "email")
        if not req.password:
            raise ValidationError("Password is required", "password")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute("SELECT id, name, email, password_hash, is_verified FROM users WHERE email = %s", (req.email,))
                    user = cursor.fetchone()
        except psycopg2.Error as e:
            log_error(e, "signin database")
            raise handle_database_error(e)
        
        if not user or not user["password_hash"]:
            logger.warning(f"Failed login attempt for email: {req.email}")
            raise AuthenticationError("Invalid email or password")
        
        if not verify_password(req.password, user["password_hash"]):
            logger.warning(f"Failed login attempt (wrong password) for email: {req.email}")
            raise AuthenticationError("Invalid email or password")
        
        if not user["is_verified"]:
            logger.warning(f"Login attempt with unverified email: {req.email}")
            raise ValidationError("Email verification pending")
        
        user_data = {"id": user["id"], "email": user["email"], "name": user["name"]}
        token = create_access_token(user_data)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            max_age=7 * 24 * 3600,
            samesite="lax",
            secure=False,
            path="/"
        )
        logger.info(f"Successful signin for email: {req.email}")
        return {"user": user_data}
    
    except (AuthenticationError, ValidationError):
        raise
    except Exception as e:
        log_error(e, "signin")
        raise DatabaseError("Sign in failed. Please try again.")

@router.post("/google")
def google_auth(req: GoogleAuthRequest, response: Response):
    """Authenticate user via Google OAuth token."""
    try:
        # Validate and verify Google token
        try:
            client_id = os.getenv("GOOGLE_CLIENT_ID", "821514705181-4j2t6hghcn168s32hoinvuo8vf1kl84i.apps.googleusercontent.com")
            idinfo = id_token.verify_oauth2_token(req.token, requests.Request(), client_id)
            
            email = idinfo.get('email')
            name = idinfo.get('name', 'Google User')
            sub = idinfo.get('sub')
            
            if not email or not sub:
                raise ValidationError("Invalid Google token data")
            
            logger.info(f"Google token verified for email: {email}")
        except GoogleAuthError as e:
            log_error(e, "google_auth token verification")
            raise handle_google_auth_error(e)
        except Exception as e:
            log_error(e, "google_auth token verification")
            raise ExternalServiceError("Google Auth", str(e))
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute("SELECT id, name, email FROM users WHERE google_sub = %s OR email = %s", (sub, email))
                    user = cursor.fetchone()
                    
                    if not user:
                        # Create new user via Google OAuth
                        cursor.execute(
                            "INSERT INTO users (name, email, google_sub, is_verified) VALUES (%s, %s, %s, TRUE) RETURNING id",
                            (name, email, sub)
                        )
                        user_id = cursor.fetchone()[0]
                        user_name = name
                        conn.commit()
                        logger.info(f"New user created via Google OAuth: {email}")
                    else:
                        # Update existing user with google_sub if not set
                        user_id = user["id"]
                        user_name = user["name"]
                        cursor.execute("UPDATE users SET google_sub = %s, is_verified = TRUE WHERE id = %s", (sub, user_id))
                        conn.commit()
                        logger.info(f"User authenticated via Google OAuth: {email}")
        except psycopg2.Error as e:
            log_error(e, "google_auth database")
            raise handle_database_error(e)
        
        user_data = {"id": user_id, "email": email, "name": user_name}
        token = create_access_token(user_data)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            max_age=7 * 24 * 3600,
            samesite="lax",
            secure=False,
            path="/"
        )
        return {"user": user_data}
    
    except (ValidationError, ExternalServiceError):
        raise
    except Exception as e:
        log_error(e, "google_auth")
        raise DatabaseError("Google authentication failed")

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}

@router.post("/signout")
def signout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"status": "success"}

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """Send password reset code to email."""
    try:
        # Validate input
        if not req.email or "@" not in req.email:
            raise ValidationError("Invalid email format", "email")
        
        import random
        otp_code = f"{random.randint(100000, 999999)}"
        otp_expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute("SELECT id FROM users WHERE email = %s", (req.email,))
                    user = cursor.fetchone()
                    
                    if not user:
                        raise ResourceNotFoundError("Email", req.email)
                    
                    cursor.execute(
                        "UPDATE users SET otp_code = %s, otp_expires_at = %s WHERE id = %s",
                        (otp_code, otp_expires_at, user["id"])
                    )
                    conn.commit()
                    logger.info(f"Password reset code sent for email: {req.email}")
        except psycopg2.Error as e:
            log_error(e, "forgot_password database")
            raise handle_database_error(e)
        
        # Send verification email
        try:
            send_otp_email(req.email, otp_code, email_type="password_reset")
        except Exception as e:
            log_error(e, "forgot_password email sending")
            logger.warning(f"Failed to send password reset email to {req.email}")
            # Don't fail the API call if email fails
        
        return {"status": "success", "message": "Password reset code sent successfully"}
    
    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        log_error(e, "forgot_password")
        raise DatabaseError("Failed to initiate password reset")

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    """Reset user password with OTP verification."""
    try:
        # Validate input
        if not req.email or "@" not in req.email:
            raise ValidationError("Invalid email format", "email")
        if not req.otp or len(req.otp) != 6 or not req.otp.isdigit():
            raise ValidationError("OTP must be a 6-digit number", "otp")
        if not req.new_password or len(req.new_password) < 6:
            raise ValidationError("Password must be at least 6 characters", "new_password")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute(
                        "SELECT id, otp_code, otp_expires_at FROM users WHERE email = %s",
                        (req.email,)
                    )
                    user = cursor.fetchone()
                    
                    if not user:
                        raise ResourceNotFoundError("User", req.email)
                    
                    if not user["otp_code"] or not user["otp_expires_at"]:
                        raise ValidationError("No reset code requested for this email")
                    
                    if user["otp_code"] != req.otp:
                        raise ValidationError("Invalid verification code", "otp")
                    
                    now = datetime.datetime.utcnow()
                    if user["otp_expires_at"] < now:
                        raise ValidationError("Verification code has expired", "otp")
                    
                    hashed = hash_password(req.new_password)
                    cursor.execute(
                        "UPDATE users SET password_hash = %s, otp_code = NULL, otp_expires_at = NULL WHERE id = %s",
                        (hashed, user["id"])
                    )
                    conn.commit()
                    logger.info(f"Password reset successful for email: {req.email}")
        except psycopg2.Error as e:
            log_error(e, "reset_password database")
            raise handle_database_error(e)
        
        return {"status": "success", "message": "Password reset successfully. You can now sign in."}
    
    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        log_error(e, "reset_password")
        raise DatabaseError("Password reset failed")

