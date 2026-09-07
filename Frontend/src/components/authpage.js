"use client";

import { useState, useEffect, useContext } from "react";
import { GoogleLogin } from "@react-oauth/google";
import { AuthContext } from "../context/AuthContext";
import { apiPost, getErrorMessage } from "../utils/api";

export default function AuthPage({ onAuthSuccess }) {
  const auth = useContext(AuthContext);
  const [mode, setMode] = useState("signIn");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [otp, setOtp] = useState("");
  const [verificationEmail, setVerificationEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState("");
  const [mounted, setMounted] = useState(false);
  const [newPassword, setNewPassword] = useState("");

  useEffect(() => {
    console.log("AuthPage mounted. Current mode:", mode);
    const timer = setTimeout(() => {
      setMounted(true);
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setLocalError("");
    
    try {
      const endpoint = mode === "signIn" ? "/api/auth/signin" : "/api/auth/signup";
      const payload = {
        email,
        password,
        ...(mode === "signUp" && { name }),
      };

      const data = await apiPost(endpoint, payload);

      if (data.status === "verification_required") {
        setVerificationEmail(data.email);
        setMode("verifyOtp");
        setOtp("");
      } else {
        auth.login(null, data.user);
        onAuthSuccess?.(data.user);
      }
    } catch (err) {
      console.error("Authentication error:", err);
      
      // Check for specific error messages indicating verification pending
      const errorMsg = getErrorMessage(err);
      if (err.message?.includes("verification pending") || errorMsg.includes("verification")) {
        setVerificationEmail(email);
        setMode("verifyOtp");
        setOtp("");
      } else {
        setLocalError(errorMsg || "Authentication failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOtpSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setLocalError("");

    try {
      const data = await apiPost("/api/auth/verify-otp", {
        email: verificationEmail,
        otp
      });

      auth.login(null, data.user);
      onAuthSuccess?.(data.user);
    } catch (err) {
      console.error("OTP verification error:", err);
      setLocalError(getErrorMessage(err) || "OTP verification failed. Please check and try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setLoading(true);
    setLocalError("");

    try {
      const data = await apiPost("/api/auth/resend-otp", {
        email: verificationEmail
      });
      alert(data.message || "Verification code resent successfully!");
    } catch (err) {
      console.error("Resend OTP error:", err);
      setLocalError(getErrorMessage(err) || "Failed to resend verification code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPasswordSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setLocalError("");

    try {
      const data = await apiPost("/api/auth/forgot-password", { email });
      setVerificationEmail(email);
      setMode("resetPassword");
      setOtp("");
      setNewPassword("");
    } catch (err) {
      console.error("Forgot password error:", err);
      setLocalError(getErrorMessage(err) || "Failed to send password reset code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleResetPasswordSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setLocalError("");

    try {
      const data = await apiPost("/api/auth/reset-password", {
        email: verificationEmail,
        otp,
        new_password: newPassword
      });
      alert("Password has been reset successfully! Please sign in with your new password.");
      setMode("signIn");
      setPassword("");
      setNewPassword("");
      setEmail(verificationEmail);
    } catch (err) {
      console.error("Reset password error:", err);
      setLocalError(getErrorMessage(err) || "Failed to reset password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    setLoading(true);
    setLocalError("");
    try {
      const jwtToken = credentialResponse.credential;
      const data = await apiPost("/api/auth/google", { token: jwtToken });

      auth.login(null, data.user);
      onAuthSuccess?.(data.user);
    } catch (err) {
      console.error("Google login error:", err);
      setLocalError(getErrorMessage(err) || "Google login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleError = () => {
    setLocalError("Google login failed. Please try again.");
    console.error("Google login failed");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md rounded-4xl border border-slate-800 bg-slate-900/95 p-8 shadow-2xl shadow-slate-950/40">
        
        {mode === "signIn" || mode === "signUp" ? (
          <>
            <div className="mb-8 flex flex-col gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-cyan-400 font-semibold">
                  Welcome to Documind
                </p>
                <h1 className="mt-3 text-3xl font-semibold">{mode === "signIn" ? "Sign In" : "Create Account"}</h1>
                <p className="mt-2 text-sm text-slate-400">
                  {mode === "signIn"
                    ? "Access your dashboard and continue your work."
                    : "Create a new account to save your workspace settings."}
                </p>
              </div>

              <div className="flex items-center rounded-3xl bg-slate-950/80 p-1 text-sm uppercase tracking-[0.22em] text-slate-400">
                <button
                  type="button"
                  onClick={() => {
                    console.log("Switching mode to signIn");
                    setMode("signIn");
                  }}
                  className={`flex-1 rounded-3xl px-4 py-3 transition cursor-pointer ${
                    mode === "signIn"
                      ? "bg-cyan-500 text-slate-950"
                      : "hover:bg-slate-800"
                  }`}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => {
                    console.log("Switching mode to signUp");
                    setMode("signUp");
                  }}
                  className={`flex-1 rounded-3xl px-4 py-3 transition cursor-pointer ${
                    mode === "signUp"
                      ? "bg-cyan-500 text-slate-950"
                      : "hover:bg-slate-800"
                  }`}
                >
                  Sign Up
                </button>
              </div>
            </div>

            <div className="mb-6 flex justify-center">
              {mounted && (
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
                  theme="filled_blue"
                  size="large"
                  shape="pill"
                />
              )}
            </div>

            {localError && (
              <div className="mb-4 rounded-3xl border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-300">
                {localError}
              </div>
            )}

            <div className="flex items-center gap-4 mb-6">
              <div className="h-px flex-1 bg-slate-700"></div>
              <span className="text-xs text-slate-500 uppercase tracking-[0.2em]">or continue with email</span>
              <div className="h-px flex-1 bg-slate-700"></div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === "signUp" && (
                <label className="block text-sm text-slate-300">
                  <span>Name</span>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                    className="mt-2 w-full rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
                  />
                </label>
              )}

              <label className="block text-sm text-slate-300">
                <span>Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="mt-2 w-full rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
                />
              </label>

              <label className="block text-sm text-slate-300">
                <span>Password</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  required
                  className="mt-2 w-full rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
                />
              </label>

              {mode === "signIn" && (
                <div className="flex items-center justify-between text-sm text-slate-400">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-cyan-500"
                    />
                    Remember me
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setMode("forgotPassword");
                      setLocalError("");
                    }}
                    className="text-cyan-400 hover:text-cyan-200 cursor-pointer"
                  >
                    Forgot?
                  </button>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-3xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {loading ? "Loading..." : mode === "signIn" ? "Sign In" : "Create Account"}
              </button>
            </form>
          </>
        ) : mode === "verifyOtp" ? (
          <>
            <div className="mb-8 flex flex-col gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-cyan-400 font-semibold">
                  Verify Email
                </p>
                <h1 className="mt-3 text-3xl font-semibold">Enter OTP Code</h1>
                <p className="mt-2 text-sm text-slate-400 text-balance">
                  We sent a 6-digit verification code to <span className="font-semibold text-white break-all">{verificationEmail}</span>.
                </p>
              </div>
            </div>

            {localError && (
              <div className="mb-4 rounded-3xl border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-300">
                {localError}
              </div>
            )}

            <form onSubmit={handleOtpSubmit} className="space-y-6">
              <label className="block text-sm text-slate-300">
                <span>Verification Code</span>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))}
                  placeholder="123456"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  required
                  className="mt-2 w-full text-center tracking-[0.5em] text-2xl font-bold rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-white outline-none transition focus:border-cyan-500 placeholder-slate-900 placeholder-tracking-[0.1em]"
                />
              </label>

              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="w-full rounded-3xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {loading ? "Verifying..." : "Verify & Continue"}
              </button>

              <div className="flex flex-col gap-3 text-center text-sm">
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={loading}
                  className="text-cyan-400 hover:text-cyan-200 font-semibold cursor-pointer disabled:opacity-50"
                >
                  Resend Verification Code
                </button>
                
                <button
                  type="button"
                  onClick={() => {
                    console.log("Going back to signIn mode");
                    setMode("signIn");
                    setLocalError("");
                  }}
                  className="text-slate-400 hover:text-slate-200 text-xs cursor-pointer"
                >
                  Back to Sign In
                </button>
              </div>
            </form>
          </>
        ) : mode === "forgotPassword" ? (
          <>
            <div className="mb-8 flex flex-col gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-cyan-400 font-semibold">
                  Forgot Password
                </p>
                <h1 className="mt-3 text-3xl font-semibold">Reset Your Password</h1>
                <p className="mt-2 text-sm text-slate-400">
                  Enter your email address and we will send you a 6-digit password reset code.
                </p>
              </div>
            </div>

            {localError && (
              <div className="mb-4 rounded-3xl border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-300">
                {localError}
              </div>
            )}

            <form onSubmit={handleForgotPasswordSubmit} className="space-y-6">
              <label className="block text-sm text-slate-300">
                <span>Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="mt-2 w-full rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
                />
              </label>

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-3xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {loading ? "Sending..." : "Send Reset Code"}
              </button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => {
                    setMode("signIn");
                    setLocalError("");
                  }}
                  className="text-slate-400 hover:text-slate-200 text-xs cursor-pointer"
                >
                  Back to Sign In
                </button>
              </div>
            </form>
          </>
        ) : (
          <>
            <div className="mb-8 flex flex-col gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-cyan-400 font-semibold">
                  Reset Password
                </p>
                <h1 className="mt-3 text-3xl font-semibold">Enter New Password</h1>
                <p className="mt-2 text-sm text-slate-400 text-balance">
                  We sent a 6-digit reset code to <span className="font-semibold text-white break-all">{verificationEmail}</span>.
                </p>
              </div>
            </div>

            {localError && (
              <div className="mb-4 rounded-3xl border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-300">
                {localError}
              </div>
            )}

            <form onSubmit={handleResetPasswordSubmit} className="space-y-4">
              <label className="block text-sm text-slate-300">
                <span>Reset Code</span>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))}
                  placeholder="123456"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  required
                  className="mt-2 w-full text-center tracking-[0.5em] text-2xl font-bold rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-white outline-none transition focus:border-cyan-500 placeholder-slate-900 placeholder-tracking-[0.1em]"
                />
              </label>

              <label className="block text-sm text-slate-300">
                <span>New Password</span>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password"
                  required
                  className="mt-2 w-full rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
                />
              </label>

              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="w-full rounded-3xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {loading ? "Resetting..." : "Reset Password"}
              </button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => {
                    setMode("signIn");
                    setLocalError("");
                  }}
                  className="text-slate-400 hover:text-slate-200 text-xs cursor-pointer"
                >
                  Back to Sign In
                </button>
              </div>
            </form>
          </>
        )}

        <div className="mt-6 border-t border-slate-800 pt-4 text-center text-sm text-slate-500">
          <p>
            By continuing, you agree to our <span className="text-cyan-400">Terms</span> and <span className="text-cyan-400">Privacy</span>.
          </p>
        </div>
      </div>
    </div>
  );
}
