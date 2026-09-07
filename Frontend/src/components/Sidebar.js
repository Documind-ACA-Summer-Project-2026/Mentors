"use client";

import { useState, useEffect, useContext, useCallback } from "react";
import { AuthContext } from "../context/AuthContext";
import { apiGet, apiPost, apiDelete } from "../utils/api";

const sidebarItems = [
  { id: "history", label: "Chat History" },
  { id: "documents", label: "Documents" },
  { id: "profile", label: "Profile" },
  { id: "settings", label: "Settings" },
];

export default function Sidebar({ isOpen = true, activeChatId, setActiveChatId }) {
  const auth = useContext(AuthContext);
  const [activePanel, setActivePanel] = useState("history");
  const [chats, setChats] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loadingChats, setLoadingChats] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploading, setUploading] = useState(false);  
  const [uploadError, setUploadError] = useState("");

  // Fetch Chats
  const fetchChats = useCallback(async () => {
    setLoadingChats(true);
    try {
      const data = await apiGet("/api/chats");
      setChats(data);
      if (data.length > 0 && !activeChatId) {
        setActiveChatId(data[0].id);
      }
    } catch (err) {
      console.error("Failed to fetch chats:", err);
    } finally {
      setLoadingChats(false);
    }
  }, [activeChatId, setActiveChatId]);

  // Fetch Documents
  const fetchDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const data = await apiGet("/api/documents");
      setDocuments(data);
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    if (auth.isAuthenticated) {
      const timer = setTimeout(() => {
        fetchChats();
        fetchDocuments();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [auth.isAuthenticated, fetchChats, fetchDocuments]);

  // Create Chat
  const handleCreateChat = async () => {
    const title = `Chat ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
    try {
      const newChat = await apiPost("/api/chats", { title });
      setChats(prev => [newChat, ...prev]);
      setActiveChatId(newChat.id);
      setActivePanel("history");
    } catch (err) {
      console.error("Failed to create chat:", err);
    }
  };

  // Delete Chat
  const handleDeleteChat = async (e, chatId) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this chat?")) return;
    try {
      await apiDelete(`/api/chats/${chatId}`);
      setChats(prev => prev.filter(c => c.id !== chatId));
      if (activeChatId === chatId) {
        const remaining = chats.filter(c => c.id !== chatId);
        setActiveChatId(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
  };

  // Upload Document
  const handleUploadDocument = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Only PDF documents are supported.");
      return;
    }

    setUploading(true);
    setUploadError("");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/documents", {
        method: "POST",
        credentials: "same-origin",
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      const newDoc = await response.json();
      setDocuments(prev => [newDoc, ...prev]);
      alert("Document indexed successfully!");
    } catch (err) {
      console.error("Upload failed:", err);
      setUploadError(err.message || "Failed to index PDF.");
    } finally {
      setUploading(false);
      // Reset input
      e.target.value = "";
    }
  };

  // Delete Document
  const handleDeleteDocument = async (docId) => {
    if (!window.confirm("Are you sure you want to delete this document? All associated context will be un-indexed.")) return;
    try {
      await apiDelete(`/api/documents/${docId}`);
      setDocuments(prev => prev.filter(d => d.id !== docId));
    } catch (err) {
      console.error("Failed to delete document:", err);
    }
  };

  // Format date helper
  const formatDate = (isoStr) => {
    try {
      const date = new Date(isoStr);
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoStr;
    }
  };

  return (
    <aside
      className={`flex-none flex flex-col h-full rounded-3xl bg-gray-900 p-3 shadow-xl overflow-hidden transition-all duration-700 ease-out ${
        isOpen ? "border border-gray-700 opacity-100 scale-100" : "border-0 opacity-0 scale-95 pointer-events-none"
      }`}
      style={{
        width: isOpen ? "380px" : "0px",
        minWidth: isOpen ? "380px" : "0px",
        padding: isOpen ? undefined : "0px",
      }}
    >
      {/* Workspace Header */}
      <div className="mb-5 px-3 py-3 rounded-3xl bg-gray-900 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-cyan-300 font-semibold">
              Sidebar
            </p>
            <h2 className="mt-2 text-white text-xl font-semibold">Documind Space</h2>
          </div>
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-2xl bg-cyan-500 text-gray-950 font-bold">
            D
          </span>
        </div>

        {/* Tab Navigation */}
        <div className="mt-4 grid grid-cols-2 gap-2">
          {sidebarItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActivePanel(item.id)}
              className={`text-center rounded-xl px-2 py-2 text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer ${
                activePanel === item.id
                  ? "bg-cyan-500 text-gray-950 shadow-lg"
                  : "bg-gray-800 text-gray-300 hover:bg-gray-700"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Panel Content */}
      <div className="flex-1 overflow-y-auto px-0 py-2">
        {/* Chat History Panel */}
        {activePanel === "history" && (
          <div className="space-y-4 px-3 py-3 rounded-3xl bg-gray-900 border border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-base font-semibold text-white">Recent Chats</h3>
                <p className="text-xs text-gray-400">Manage your active sessions.</p>
              </div>
              <button
                onClick={handleCreateChat}
                className="bg-cyan-500 hover:bg-cyan-400 text-gray-950 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer"
              >
                + New Chat
              </button>
            </div>

            {loadingChats ? (
              <p className="text-sm text-cyan-400 text-center py-4">Loading chats...</p>
            ) : chats.length === 0 ? (
              <div className="text-center py-8 text-gray-500 text-sm">
                No chats found. Click &quot;New Chat&quot; to start!
              </div>
            ) : (
              <div className="space-y-2 max-h-87.5 overflow-y-auto pr-1">
                {chats.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => setActiveChatId(item.id)}
                    className={`group cursor-pointer rounded-2xl border p-3 flex items-center justify-between gap-2 transition-all ${
                      activeChatId === item.id
                        ? "border-cyan-500 bg-gray-800 text-white"
                        : "border-gray-800 bg-gray-800/40 text-gray-300 hover:bg-gray-850 hover:border-gray-700"
                    }`}
                  >
                    <div className="overflow-hidden">
                      <h4 className="font-semibold text-sm truncate">{item.title}</h4>
                      <p className="text-[11px] text-gray-500 mt-1">{formatDate(item.created_at)}</p>
                    </div>
                    <button
                      onClick={(e) => handleDeleteChat(e, item.id)}
                      className="text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity p-1 cursor-pointer"
                      title="Delete chat"
                    >
                      🗑️
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Documents/RAG Files Panel */}
        {activePanel === "documents" && (
          <div className="space-y-4 px-3 py-3 rounded-3xl bg-gray-900 border border-gray-700">
            <div>
              <h3 className="text-base font-semibold text-white">Knowledge Source</h3>
              <p className="text-xs text-gray-400">Upload PDFs to index them into your private vector database.</p>
            </div>

            {/* Upload Area */}
            <div className="rounded-2xl border border-dashed border-gray-700 bg-gray-800/45 p-4 text-center">
              <label className="cursor-pointer block">
                <span className="text-2xl block mb-1">📁</span>
                <span className="text-xs text-cyan-400 font-semibold block">
                  {uploading ? "Indexing file..." : "Click to Upload PDF"}
                </span>
                <span className="text-[10px] text-gray-500 block mt-1">Max size 10MB</span>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleUploadDocument}
                  disabled={uploading}
                  className="hidden"
                />
              </label>
            </div>

            {uploadError && (
              <p className="text-xs text-red-400 text-center px-2">{uploadError}</p>
            )}
  
            {/* List of Documents */}
            <div className="space-y-2">
              <h4 className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Indexed PDFs</h4>
              {loadingDocs ? (
                <p className="text-xs text-cyan-400 text-center py-2">Loading documents...</p>
              ) : documents.length === 0 ? (
                <div className="text-center py-4 text-xs text-gray-500">
                  No custom documents uploaded. The default general knowledge PDF is active.
                </div>
              ) : (
                <div className="space-y-2 max-h-55 overflow-y-auto pr-1">
                  {documents.map((doc) => (
                    <div key={doc.id} className="rounded-2xl border border-gray-850 bg-gray-850/50 p-2.5 flex items-center justify-between gap-2">
                      <div className="overflow-hidden">
                        <p className="text-xs font-semibold text-white truncate" title={doc.filename}>{doc.filename}</p>
                        <p className="text-[10px] text-gray-500 mt-0.5">{formatDate(doc.upload_time)}</p>
                      </div>
                      <button
                        onClick={() => handleDeleteDocument(doc.id)}
                        className="text-gray-500 hover:text-red-400 p-1 text-xs cursor-pointer"
                        title="Remove document"
                      >
                        ❌
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* User Profile Panel */}
        {activePanel === "profile" && (
          <div className="space-y-4 px-3 py-3 rounded-3xl bg-gray-900 border border-gray-700">
            <div className="flex items-center gap-3">
              <div className="h-14 w-14 rounded-3xl bg-cyan-500 flex items-center justify-center text-xl font-bold text-gray-950">
                {(auth.user?.name || "U")[0].toUpperCase()}
              </div>
              <div>
                <h3 className="text-white text-lg font-semibold">{auth.user?.name || "User"}</h3>
                <p className="text-sm text-gray-400">Authenticated Member</p>
              </div>
            </div>
            <div className="space-y-2 rounded-3xl border border-gray-800 bg-gray-800 p-3">
              <div className="flex items-center justify-between text-sm text-gray-300">
                <span>Email</span>
                <span className="text-xs truncate max-w-50">{auth.user?.email || "N/A"}</span>
              </div>
              <div className="flex items-center justify-between text-sm text-gray-300">
                <span>Account Type</span>
                <span className="text-xs">Standard</span>
              </div>
            </div>
            
            <button
              onClick={auth.logout}
              className="w-full bg-red-600 hover:bg-red-700 text-white rounded-2xl py-2.5 text-sm font-semibold transition cursor-pointer"
            >
              Sign Out
            </button>
          </div>
        )}

        {/* Preferences / Settings Panel */}
        {activePanel === "settings" && (
          <div className="space-y-4 px-3 py-3 rounded-3xl bg-gray-900 border border-gray-700">
            <div>
              <h3 className="text-base font-semibold text-white">Preferences</h3>
              <p className="text-sm text-gray-400">Adjust workspace actions.</p>
            </div>
            <div className="space-y-2 rounded-3xl border border-gray-800 bg-gray-800 p-3">
              <div className="flex items-center justify-between gap-3 text-sm text-gray-300">
                <span>Dark mode</span>
                <span className="rounded-full bg-gray-700 px-3 py-1 text-[10px]">Enabled</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-sm text-gray-300">
                <span>Notifications</span>
                <span className="rounded-full bg-gray-700 px-3 py-1 text-[10px]">On</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
