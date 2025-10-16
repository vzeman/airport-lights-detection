import * as React from "react"
import { SidebarTrigger } from "./ui/sidebar"

export function SiteHeader() {
  return (
    <header className="flex h-16 shrink-0 items-center gap-2 px-4">
      <SidebarTrigger className="-ml-1" />
      <div className="flex flex-1 items-center gap-2">
        {/* Additional header content can go here */}
      </div>
    </header>
  )
}