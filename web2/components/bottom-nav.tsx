"use client"

import { Home, ListChecks, Target, Plus, User } from "lucide-react"
import { useTranslation } from "@/lib/i18n"

interface BottomNavProps {
  activeTab: "home" | "tasks" | "goals" | "profile"
  onTabChange: (tab: "home" | "tasks" | "goals" | "profile") => void
  onOpenAddTask?: () => void
  userLang?: string | null
}

export function BottomNav({ activeTab, onTabChange, onOpenAddTask, userLang }: BottomNavProps) {
  const t = useTranslation(userLang || "uz")
  
  const navItems = [
    { id: "home" as const, icon: Home, label: t("Dashboard") },
    { id: "tasks" as const, icon: ListChecks, label: t("Tasks") },
    { id: "goals" as const, icon: Target, label: t("Dreams") },
    { id: "profile" as const, icon: User, label: t("Profile") },
  ]

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-card/80 backdrop-blur-xl border-t border-border/50 pb-safe z-50">
      <div className="max-w-md mx-auto px-2 py-2">
        <div className="flex items-center justify-between w-full">
          {/* Left two tabs */}
          {navItems.slice(0, 2).map((item) => (
            <div key={item.id} className="flex items-center flex-1 justify-center">
              <button
                onClick={() => onTabChange(item.id)}
                className={`flex flex-col items-center justify-center gap-1 px-1 py-1 rounded-xl transition-all w-full max-w-[64px] ${
                  activeTab === item.id 
                    ? 'text-primary' 
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <item.icon className={`h-6 w-6 shrink-0 transition-transform ${activeTab === item.id ? 'scale-110' : ''}`} />
                <span className={`text-[10px] leading-tight font-medium whitespace-nowrap overflow-hidden text-ellipsis w-full text-center ${activeTab === item.id ? 'opacity-100' : 'opacity-70'}`}>
                  {item.label}
                </span>
              </button>
            </div>
          ))}

          {/* Central Plus (FAB) Button */}
          <div className="flex items-center flex-1 justify-center">
            <button 
              onClick={onOpenAddTask}
              className="w-14 h-14 shrink-0 rounded-full bg-primary flex items-center justify-center shadow-lg shadow-primary/30 -mt-8 transition-transform active:scale-95 hover:scale-105"
            >
              <Plus className="h-6 w-6 text-primary-foreground" />
            </button>
          </div>

          {/* Right two tabs */}
          {navItems.slice(2).map((item) => (
            <div key={item.id} className="flex items-center flex-1 justify-center">
              <button
                onClick={() => onTabChange(item.id)}
                className={`flex flex-col items-center justify-center gap-1 px-1 py-1 rounded-xl transition-all w-full max-w-[64px] ${
                  activeTab === item.id 
                    ? 'text-primary' 
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <item.icon className={`h-6 w-6 shrink-0 transition-transform ${activeTab === item.id ? 'scale-110' : ''}`} />
                <span className={`text-[10px] leading-tight font-medium whitespace-nowrap overflow-hidden text-ellipsis w-full text-center ${activeTab === item.id ? 'opacity-100' : 'opacity-70'}`}>
                  {item.label}
                </span>
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
