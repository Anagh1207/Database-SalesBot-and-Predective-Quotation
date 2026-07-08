import React from "react";
import Sidebar from "./Sidebar";

interface ShellProps {
  children: React.ReactNode;
  onNewChat?: () => void;
}

export default function Shell({ children, onNewChat }: ShellProps) {
  return (
    <div className="w-full min-h-screen h-screen overflow-hidden bg-app-bg flex font-sans">
      {/* Collapsible Sidebar */}
      <Sidebar onNewChat={onNewChat} />

      {/* Main Content Workspace Container */}
      <div className="flex-1 h-screen overflow-hidden flex flex-col min-w-0">
        {children}
      </div>
    </div>
  );
}
