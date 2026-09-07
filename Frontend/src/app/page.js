"use client";

import { useState, useEffect } from 'react';
import Navbar from '../components/navbar';
import Footer from '../components/footer';
import Chat from '../components/Chat';
import Sidebar from '../components/Sidebar';
import AuthPage from '../components/authpage';
import { useAuth } from '../context/AuthContext';

export default function Home() {
  const { isAuthenticated, loading, user } = useAuth();
  const [showSidebar, setShowSidebar] = useState(true);
  const [activeChatId, setActiveChatId] = useState(null);

  // Reset active chat when user logs out or switches accounts
  useEffect(() => {
    setActiveChatId(null);
  }, [user?.id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center font-sans">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-cyan-500"></div>
          <p className="text-sm tracking-wider text-gray-400">LOADING DOCUMIND...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  return (
    <>
      <Navbar onToggleSidebar={() => setShowSidebar((open) => !open)} sidebarOpen={showSidebar} />

      <main className="pt-20 pb-9 bg-gray-900 px-2 h-screen overflow-hidden">
        <div className={`w-full px-3 h-full overflow-hidden flex items-stretch ${showSidebar ? 'gap-4' : 'gap-0'}`}>
          <Sidebar 
            isOpen={showSidebar} 
            activeChatId={activeChatId} 
            setActiveChatId={setActiveChatId} 
          />
          <div className="flex-1 flex justify-center">
            <Chat 
              activeChatId={activeChatId} 
              setActiveChatId={setActiveChatId}
            />
          </div>
        </div>
      </main>

      <Footer />
    </>
  );
}
