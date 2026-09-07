from pydantic import BaseModel

class SignupRequest(BaseModel):
    email: str
    password: str
    name: str

class SigninRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    token: str

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str

class ResendOtpRequest(BaseModel):
    email: str

class CreateChatRequest(BaseModel):
    title: str

class ChatRequest(BaseModel):
    chat_id: str
    message: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

