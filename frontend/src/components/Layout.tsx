import React from 'react'
import { Outlet } from 'react-router-dom'
import { AppSidebar } from './app-sidebar'
import { SiteHeader } from './site-header'
import {
  SidebarInset,
  SidebarProvider,
} from './ui/sidebar'

const Layout: React.FC = () => {
  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "16rem",
          "--header-height": "4rem",
        } as React.CSSProperties
      }
    >
      <div className="no-print">
        <AppSidebar variant="inset" />
      </div>
      <SidebarInset>
        <div className="no-print">
          <SiteHeader />
        </div>
        <div className="flex flex-1 flex-col">
          <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
            <Outlet />
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

export default Layout