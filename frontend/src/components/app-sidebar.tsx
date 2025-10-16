import * as React from "react"
import { Link, useLocation } from "react-router-dom"
import {
  Plane,
  LayoutDashboard,
  Users,
  Map,
  ClipboardList,
  Settings,
  Package,
  MapPin,
  ChevronRight,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "./ui/sidebar"
import { useAuth } from "../contexts/AuthContext"
import { Avatar, AvatarFallback } from "./ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "./ui/dropdown-menu"
import { User, LogOut } from "lucide-react"

// Menu items with proper grouping
const data = {
  navMain: [
    {
      title: "Overview",
      items: [
        {
          title: "Dashboard",
          url: "/",
          icon: LayoutDashboard,
          isActive: false,
          roles: ['all']
        },
      ],
    },
    {
      title: "Airport Management",
      items: [
        {
          title: "Airports",
          url: "/airports",
          icon: Plane,
          isActive: false,
          roles: ['all']
        },
        {
          title: "Mission Planning",
          url: "/mission-planning",
          icon: MapPin,
          isActive: false,
          roles: ['all']
        },
        {
          title: "Map View",
          url: "/map",
          icon: Map,
          isActive: false,
          roles: ['all']
        },
      ],
    },
    {
      title: "Operations",
      items: [
        {
          title: "Tasks",
          url: "/tasks",
          icon: ClipboardList,
          isActive: false,
          roles: ['all']
        },
      ],
    },
    {
      title: "Administration",
      items: [
        {
          title: "Users",
          url: "/users",
          icon: Users,
          isActive: false,
          roles: ['admin']
        },
        {
          title: "Item Types",
          url: "/item-types",
          icon: Package,
          isActive: false,
          roles: ['admin']
        },
        {
          title: "Settings",
          url: "/settings",
          icon: Settings,
          isActive: false,
          roles: ['all']
        },
      ],
    },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const location = useLocation()
  const { user, logout, isSuperAdmin, isAirportAdmin } = useAuth()

  const handleLogout = () => {
    logout()
  }

  const filterMenuItemsByRole = (items: typeof data.navMain[0]['items']) => {
    return items.filter(item => {
      if (item.roles.includes('all')) return true
      if (item.roles.includes('admin') && (isSuperAdmin || isAirportAdmin)) return true
      return false
    })
  }

  return (
    <Sidebar variant="inset" {...props}>
      <SidebarHeader>
        <div className="flex items-center gap-2 px-4 py-2">
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
            <Plane className="size-4" />
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-semibold">Airport Management</span>
            <span className="truncate text-xs">Drone Inspection System</span>
          </div>
        </div>
      </SidebarHeader>
      
      <SidebarContent>
        {data.navMain.map((group) => {
          const filteredItems = filterMenuItemsByRole(group.items)
          if (filteredItems.length === 0) return null
          
          return (
            <SidebarGroup key={group.title}>
              <SidebarGroupLabel>{group.title}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {filteredItems.map((item) => {
                    const isActive = location.pathname === item.url || 
                      (item.url !== '/' && location.pathname.startsWith(item.url))
                    
                    return (
                      <SidebarMenuItem key={item.title}>
                        <SidebarMenuButton asChild isActive={isActive}>
                          <Link to={item.url}>
                            <item.icon />
                            <span>{item.title}</span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    )
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )
        })}
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                >
                  <Avatar className="h-8 w-8 rounded-lg">
                    <AvatarFallback className="rounded-lg">
                      {user?.first_name?.[0]}{user?.last_name?.[0]}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-semibold">
                      {user?.first_name} {user?.last_name}
                    </span>
                    <span className="truncate text-xs">{user?.role}</span>
                  </div>
                  <ChevronRight className="ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
                side="bottom"
                align="end"
                sideOffset={4}
              >
                <DropdownMenuItem asChild>
                  <Link to="/profile">
                    <User />
                    Profile
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleLogout}>
                  <LogOut />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}