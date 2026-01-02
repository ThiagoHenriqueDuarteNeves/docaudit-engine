import React, { ReactNode } from 'react';
import { Sidebar } from './Sidebar';

interface MainLayoutProps {
    children: ReactNode;
    sidebarProps: React.ComponentProps<typeof Sidebar>;
}

export function MainLayout({ children, sidebarProps }: MainLayoutProps) {
    return (
        <div className="flex h-screen bg-gray-950 text-white overflow-hidden font-sans">
            <Sidebar {...sidebarProps} />

            <main className="flex-1 flex flex-col relative w-full h-full overflow-hidden">
                {children}
            </main>
        </div>
    );
}
