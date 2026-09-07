"use client";

import { useState, useRef, useEffect } from "react";
import { apiGet, getErrorMessage } from "../utils/api";

export default function Chat({ activeChatId }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [loadingMessages, setLoadingMessages] = useState(false);
    const [error, setError] = useState(null);
    const [errorDetails, setErrorDetails] = useState(null);
    
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);

    // Fetch Messages when activeChatId changes
    useEffect(() => {
        if (!activeChatId) {
            const timer = setTimeout(() => {
                setMessages([]);
                setError(null);
            }, 0);
            return () => clearTimeout(timer);
        }

        const fetchMessages = async () => {
            setLoadingMessages(true);
            setError(null);
            try {
                const data = await apiGet(`/api/chats/${activeChatId}/messages`);
                setMessages(
                    data.map(m => ({
                        id: m.id,
                        from: m.from_user ? "user" : "bot",
                        text: m.text
                    }))
                );
            } catch (err) {
                console.error("Failed to load messages:", err);
                setError("Failed to load chat history");
                setErrorDetails(getErrorMessage(err));
                setMessages([]);
            } finally {
                setLoadingMessages(false);
            }
        };

        fetchMessages();
    }, [activeChatId]);

    // Scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({
            behavior: "smooth",
        });
    }, [messages, loading]);

    // Adjust textarea height automatically
    useEffect(() => {
        const textarea = textareaRef.current;
        if (!textarea) return;

        textarea.style.height = "auto";
        const maxHeight = 160;

        if (textarea.scrollHeight > maxHeight) {
            textarea.style.height = `${maxHeight}px`;
            textarea.style.overflowY = "auto";
        } else {
            textarea.style.height = `${textarea.scrollHeight}px`;
            textarea.style.overflowY = "hidden";
        }
    }, [input]);

    const handleChange = (e) => {
        setInput(e.target.value);
    };

    const send = async () => {
        if (!input.trim() || !activeChatId || loading) return;

        const userMsgText = input.trim();
        const userMsgId = String(Date.now());
        const userMsg = {
            id: userMsgId,
            from: "user",
            text: userMsgText,
        };

        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setError(null);
        setLoading(true);

        requestAnimationFrame(() => {
            if (textareaRef.current) {
                textareaRef.current.style.height = "auto";
                textareaRef.current.style.overflowY = "hidden";
            }
        });

        // Create a unique temporary ID for the bot's incoming message
        const botMsgId = String(Date.now() + 1);

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    chat_id: activeChatId,
                    message: userMsgText
                }),
                credentials: "same-origin",
                timeout: 60000 // 60 second timeout for streaming
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || errData.message || "Server error occurred");
            }

            // Append bot message placeholder
            setMessages((prev) => [
                ...prev,
                {
                    id: botMsgId,
                    from: "bot",
                    text: "",
                },
            ]);

            // Turn off initial loading state to hide thinking indicator as we stream
            setLoading(false);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let accumulatedText = "";
            let hasError = false;
            let streamFinished = false;
            let pendingLine = "";

            try {
                while (!streamFinished) {
                    const { value, done } = await reader.read();
                    if (done) {
                        pendingLine += decoder.decode();
                        if (pendingLine.trim() === "data: [DONE]") {
                            streamFinished = true;
                        }
                        break;
                    }

                    pendingLine += decoder.decode(value, { stream: true });
                    const lines = pendingLine.split("\n");
                    pendingLine = lines.pop() || "";

                    for (const line of lines) {
                        const trimmedLine = line.trim();
                        if (trimmedLine.startsWith("data: ")) {
                            const dataStr = trimmedLine.slice(6).trim();
                            if (dataStr === "[DONE]") {
                                streamFinished = true;
                                break;
                            }
                            try {
                                const parsed = JSON.parse(dataStr);
                                if (parsed.text) {
                                    accumulatedText += parsed.text;
                                    setMessages((prev) =>
                                        prev.map((msg) =>
                                            msg.id === botMsgId
                                                ? { ...msg, text: accumulatedText }
                                                : msg
                                        )
                                    );
                                } else if (parsed.error) {
                                    hasError = true;
                                    console.warn("Stream error:", parsed.error);
                                    accumulatedText = `⚠️ Error: ${parsed.error}`;
                                    setMessages((prev) =>
                                        prev.map((msg) =>
                                            msg.id === botMsgId
                                                ? { ...msg, text: accumulatedText }
                                                : msg
                                        )
                                    );
                                    setError("Failed to process request");
                                    setErrorDetails(parsed.error);
                                    break;
                                }
                            } catch (parseErr) {
                                // Suppress parsing errors for partial segments
                                console.debug("Parse error for chunk:", parseErr);
                            }
                        }
                    }
                }
            } catch (streamErr) {
                console.error("Stream reading error:", streamErr);
                if (!hasError) {
                    setError("Stream interrupted");
                    setErrorDetails("Connection was interrupted while streaming response");
                    setMessages((prev) => {
                        const exists = prev.some(m => m.id === botMsgId);
                        if (exists) {
                            return prev.map(msg =>
                                msg.id === botMsgId
                                    ? { ...msg, text: "⚠️ Error: Connection was interrupted. Please try again." }
                                    : msg
                            );
                        }
                        return prev;
                    });
                }
            } finally {
                setLoading(false);
            }
        } catch (err) {
            console.error("Chat error:", err);
            
            const errorMsg = getErrorMessage(err);
            setLoading(false);
            setError("Failed to send message");
            setErrorDetails(errorMsg);
            
            setMessages((prev) => {
                const exists = prev.some(m => m.id === botMsgId);
                if (exists) {
                    return prev.map(msg => 
                        msg.id === botMsgId 
                            ? { ...msg, text: `⚠️ Error: ${errorMsg}` }
                            : msg
                    );
                } else {
                    return [
                        ...prev,
                        {
                            id: botMsgId,
                            from: "bot",
                            text: `⚠️ Error: ${errorMsg}`,
                        }
                    ];
                }
            });
        } finally {
            setLoading(false);
        }
    };

    function onKeyDown(e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    }

    if (!activeChatId) {
        return (
            <div className="flex flex-col h-full w-full rounded-2xl overflow-hidden shadow-xl border border-gray-700 bg-gray-800 justify-center items-center p-8 text-center text-gray-400">
                <div className="text-5xl mb-4">💬</div>
                <h3 className="text-lg font-bold text-white mb-2">Documind RAG Assistant</h3>
                <p className="text-sm max-w-sm">
                    Select a chat session from the sidebar history or create a new session to begin asking questions about your indexed documents.
                </p>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full w-full rounded-2xl overflow-hidden shadow-xl border border-gray-700 bg-gray-800">
            {/* Header */}
            <div className="px-4 py-3 bg-gray-900 text-white flex items-center justify-between border-b border-gray-700">
                <h2 className="font-semibold text-base">Documind Chatbot</h2>
                <span className="text-xs text-green-400">● Online</span>
            </div>

            {/* Error Banner */}
            {error && (
                <div className="bg-red-900/30 border-b border-red-700 px-4 py-3">
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="text-sm font-semibold text-red-400">{error}</p>
                            {errorDetails && (
                                <p className="text-xs text-red-300 mt-1">{errorDetails}</p>
                            )}
                        </div>
                        <button
                            onClick={() => setError(null)}
                            className="text-red-400 hover:text-red-300 ml-2"
                        >
                            ✕
                        </button>
                    </div>
                </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-3 scrollbar-thumb-cyan-600 space-y-3">
                {loadingMessages ? (
                    <div className="text-center text-sm text-cyan-400 py-8">Loading history...</div>
                ) : messages.length === 0 ? (
                    <div className="text-center text-sm text-gray-500 py-8">No messages yet. Ask a question to begin!</div>
                ) : (
                    messages.map((m) => (
                        <div
                            key={m.id}
                            className={`flex ${m.from === "user" ? "justify-end" : "justify-start"}`}
                        >
                            <div
                                className={`max-w-[75%] px-3 py-2 rounded-2xl whitespace-pre-wrap overflow-wrap ${
                                    m.from === "user"
                                        ? "bg-blue-600 text-white rounded-br-sm"
                                        : m.text.startsWith("⚠️") ? "bg-red-900/50 text-red-200 rounded-bl-sm"
                                        : "bg-gray-700 text-gray-100 rounded-bl-sm"
                                    }`}
                            >
                                {m.text || <span className="text-xs text-gray-450 italic">Streaming...</span>}
                            </div>
                        </div>
                    ))
                )}

                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-gray-700 text-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[75%] flex items-center gap-1.5">
                            <span className="text-xs text-cyan-300">Documind is thinking</span>
                            <span className="h-1.5 w-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                            <span className="h-1.5 w-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                            <span className="h-1.5 w-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t border-gray-700 bg-gray-900 p-3">
                <div className="flex items-end gap-2 rounded-2xl border border-gray-700 bg-gray-800 px-3 py-2">
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={handleChange}
                        onKeyDown={onKeyDown}
                        rows={1}
                        disabled={loading}
                        placeholder="Ask a question about your documents..."
                        className="flex-1 min-h-5 max-h-32 resize-none overflow-y-auto bg-transparent text-white placeholder-gray-400 outline-none leading-6 py-1 scrollbar-none disabled:opacity-50"
                    />
                    <button
                        onClick={send}
                        disabled={loading || !input.trim()}
                        className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-400 transition-colors text-white px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer"
                    >
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
}
