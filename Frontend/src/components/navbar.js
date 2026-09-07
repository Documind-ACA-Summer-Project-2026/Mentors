"use client";

import React from 'react';

const Navbar = ({ onToggleSidebar, sidebarOpen }) => {
    return (
        <div className="fixed top-0 left-0 w-full z-50 px-4 py-2">
            <nav className="bg-gray-800 rounded-2xl px-6 py-3">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex items-center justify-between gap-4">
                        <h1 className="text-white font-bold text-xl cursor-pointer">
                            Documind
                        </h1>
                        <button
                            onClick={onToggleSidebar}
                            className="rounded-2xl border border-cyan-500 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-500 hover:text-gray-950 cursor-pointer"
                        >
                            {sidebarOpen ? 'Hide Sidebar' : 'Show Sidebar'}
                        </button>
                    </div>

                    <ul className="flex items-center gap-8 text-white">
                        <li className="cursor-pointer hover:text-gray-300"> <a href="https://github.com/Documind-ACA-Summer-Project-2026" target='1'>About</a></li>
                        <li className="cursor-pointer hover:text-gray-300"> <a href="https://github.com/orgs/Documind-ACA-Summer-Project-2026/people" target='2'>Contact</a></li>
                    </ul>
                </div>
            </nav>
        </div>
    );
};

export default Navbar;
