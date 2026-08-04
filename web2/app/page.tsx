"use client"

import { useEffect, useState } from "react"
import { Dashboard } from "@/components/dashboard"
import { Discipline } from "@/components/discipline"
import { DreamBox } from "@/components/dream-box"
import { Profile } from "@/components/profile"
import { BottomNav } from "@/components/bottom-nav"
import { AddTaskDrawer } from "@/components/add-task-drawer"
import { AddGoalDrawer } from "@/components/add-goal-drawer"
import { useTelegram } from "@/lib/telegram-provider"
import { getUserData, createDream, getDashboardStats, tgFetch } from "@/lib/api"
import { CheckSquare, Target } from "lucide-react"
import { useTranslation } from "@/lib/i18n"

import { useRouter } from "next/navigation"

export default function Home() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<"home" | "tasks" | "goals" | "profile">("home")
  const [isAddTaskOpen, setIsAddTaskOpen] = useState(false)
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false)
  const [taskRefreshTrigger, setTaskRefreshTrigger] = useState(0)
  const [goalRefreshTrigger, setGoalRefreshTrigger] = useState(0)
  const { user, isLoading } = useTelegram()
  const [debug, setDebug] = useState<any>(null)
  
  const [isRegistered, setIsRegistered] = useState<boolean | null>(null)
  const [hasPremium, setHasPremium] = useState<boolean | null>(null)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [userLang, setUserLang] = useState<string | null>(null)
  const t = useTranslation(userLang || user?.language_code || "uz")

  const targetUserId = user?.id || (typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get("user_id") : null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const isTelegram = !!(window as any).Telegram?.WebApp?.initData;
      const isLocalDev = process.env.NODE_ENV === "development";
      if (!isTelegram && !isLocalDev) {
        window.location.href = "https://disciplix.uz";
      }
    }
  }, []);

  useEffect(() => {
    if (isLoading) return;
    if (targetUserId) {
      getDashboardStats(targetUserId)
        .then((res) => {
           if (res.error === "User not found") setIsRegistered(false)
           else if (res.error === "Premium required") setHasPremium(false)
           else {
               setIsRegistered(true)
               setHasPremium(true)
               if (res.user_language) setUserLang(res.user_language)
           }
           setCheckingAuth(false)
        })
        .catch((err) => {
           if (err.message === "User not found" || String(err).includes("User not found") || String(err).includes("404")) {
               setIsRegistered(false)
           } else if (err.message === "Premium required" || String(err).includes("Premium required") || String(err).includes("403")) {
               setHasPremium(false)
           } else {
               setIsRegistered(true)
               setHasPremium(true)
           }
           setCheckingAuth(false)
        })
    } else {
       setIsRegistered(false)
       setCheckingAuth(false)
    }
  }, [targetUserId, isLoading])

  useEffect(() => {
    if (typeof window === "undefined") return
    const params = new URLSearchParams(window.location.search)
    if (params.get("debug") !== "1") return

    const userIdFromQuery = params.get("user_id")
    const authHeader = (window as any).Telegram?.WebApp?.initData
      ? "initData"
      : (userIdFromQuery ? "TEST_MODE_DISCIPLIX" : "missing")

    const apiBase = process.env.NEXT_PUBLIC_API_URL || ""
    const currentUserId = user?.id || (userIdFromQuery ? Number(userIdFromQuery) : null)
    setDebug({
      apiBase,
      userId: currentUserId,
      auth: authHeader,
      isLoading,
      href: window.location.href,
      origin: window.location.origin,
      userAgent: navigator.userAgent,
      online: navigator.onLine,
    })

    if (currentUserId) {
      getUserData(currentUserId)
        .then((res) => {
          setDebug((prev: any) => ({ ...prev, userData: res }))
        })
        .catch((err) => {
          setDebug((prev: any) => ({ ...prev, error: err?.message || String(err) }))
        })

      const fullUrl = `${apiBase}/api/user_data/${currentUserId}`
      const headers = new Headers()
      if (authHeader === "initData" && (window as any).Telegram?.WebApp?.initData) {
        headers.set("Authorization", (window as any).Telegram.WebApp.initData)
      } else if (authHeader === "TEST_MODE_DISCIPLIX") {
        headers.set("Authorization", "TEST_MODE_DISCIPLIX")
      }

      fetch(fullUrl, { headers })
        .then(async (resp) => {
          const text = await resp.text()
          setDebug((prev: any) => ({
            ...prev,
            directFetch: { status: resp.status, ok: resp.ok, body: text.slice(0, 500) },
          }))
        })
        .catch((err) => {
          setDebug((prev: any) => ({
            ...prev,
            directFetch: { error: err?.message || String(err) },
          }))
        })

      fetch(fullUrl, { mode: "no-cors" as RequestMode })
        .then(() => {
          setDebug((prev: any) => ({ ...prev, noCorsFetch: "ok" }))
        })
        .catch((err) => {
          setDebug((prev: any) => ({ ...prev, noCorsFetch: err?.message || String(err) }))
        })
    }
  }, [user?.id, isLoading])

  if (checkingAuth) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center bg-[#F8F9FB] text-[#10B981]">
         <div className="w-8 h-8 border-4 border-current border-t-transparent rounded-full animate-spin"></div>
      </div>
    )
  }

  if (isRegistered === false) {
    return (
      <div className="min-h-[100dvh] flex flex-col items-center justify-center px-6 text-center bg-[#F8F9FB] max-w-md mx-auto">
          <div className="w-24 h-24 bg-emerald-100 rounded-full flex items-center justify-center mb-6">
             <span className="text-4xl">⚠️</span>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">{t("Not Registered Title")}</h2>
          <p className="text-gray-500 text-sm mb-10 leading-relaxed">{t("Not Registered Desc")}</p>
          
          <button 
              onClick={() => {
                  router.push(`/register?user_id=${targetUserId || ""}`);
              }}
              className="w-full h-14 bg-[#10B981] hover:bg-emerald-600 text-white rounded-2xl font-bold text-lg shadow-lg shadow-emerald-500/20 active:scale-[0.98] transition-transform">
              {t("Register Button")}
          </button>
      </div>
    )
  }

  if (hasPremium === false) {
    return (
      <div className="min-h-[100dvh] flex flex-col items-center justify-center px-6 text-center bg-[#F8F9FB] max-w-md mx-auto">
          <div className="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center mb-6">
             <span className="text-4xl">💎</span>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">{t("Premium Expired Title")}</h2>
          <p className="text-gray-500 text-sm mb-10 leading-relaxed">{t("Premium Expired Desc")}</p>
          
          <button 
              onClick={() => {
                  if (targetUserId) {
                      tgFetch(`/api/buy_premium?user_id=${targetUserId}`, { method: 'POST' }).catch(() => {});
                  }
                  if (typeof window !== 'undefined' && (window as any).Telegram?.WebApp?.close) {
                     (window as any).Telegram.WebApp.close();
                  }
              }}
              className="w-full h-14 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white rounded-2xl font-bold text-lg shadow-lg shadow-blue-500/20 active:scale-[0.98] transition-transform flex items-center justify-center gap-2">
              <span className="text-xl">💎</span> {t("Buy Premium Button")}
          </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex flex-col max-w-md mx-auto">
      {debug && (
        <div className="p-3 text-xs bg-amber-50 border-b border-amber-200 whitespace-pre-wrap">
          {JSON.stringify(debug, null, 2)}
        </div>
      )}
      <main className="flex-1 overflow-y-auto pb-24">
        {activeTab === "home" && <Dashboard onGoToProfile={() => setActiveTab("profile")} />}
        {activeTab === "tasks" && <Discipline refreshTrigger={taskRefreshTrigger} />}
        {activeTab === "goals" && <DreamBox refreshTrigger={goalRefreshTrigger} />}
        {activeTab === "profile" && <Profile />}
      </main>
      
      {/* FAB MODAL MENU */}
      {isAddMenuOpen && (
        <>
          <div className="fixed inset-0 bg-black/20 z-[60] backdrop-blur-sm transition-opacity" onClick={() => setIsAddMenuOpen(false)}></div>
          <div className="fixed bottom-32 right-1/2 translate-x-1/2 z-[70] flex flex-col space-y-3 items-center">
             <button 
                onClick={() => { setIsAddTaskOpen(true); setIsAddMenuOpen(false); }}
                className="flex items-center space-x-3 bg-white shadow-xl px-5 py-3 rounded-full text-[13px] font-bold text-gray-800">
              <div className="w-8 h-8 rounded-full bg-indigo-50 text-indigo-500 flex items-center justify-center font-black"><CheckSquare className="w-4 h-4"/></div>
              <span>{t("Tasks") || "Vazifa qo'shish"} +</span>
            </button>
            <button 
                onClick={() => { router.push('/add-goal'); setIsAddMenuOpen(false); }}
                className="flex items-center space-x-3 bg-white shadow-xl px-5 py-3 rounded-full text-[13px] font-bold text-gray-800">
              <div className="w-8 h-8 rounded-full bg-[#E8F8F3] text-[#10B981] flex items-center justify-center font-black"><Target className="w-4 h-4"/></div>
              <span>{t("Dreams") || "Maqsad qo'shish"} +</span>
            </button>
          </div>
        </>
      )}

      <BottomNav 
        activeTab={activeTab} 
        onTabChange={setActiveTab} 
        onOpenAddTask={() => setIsAddMenuOpen(true)}
        userLang={userLang}
      />
      <AddTaskDrawer 
        isOpen={isAddTaskOpen} 
        onClose={() => setIsAddTaskOpen(false)} 
        onTaskAdded={() => setTaskRefreshTrigger(prev => prev + 1)} 
      />
    </div>
  )
}
