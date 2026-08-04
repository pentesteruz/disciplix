"use client"

import { useState, useEffect } from "react"
import { Target, Car, Calendar, Wallet, CheckSquare, ChevronRight, Loader2 } from "lucide-react"
import { useTelegram } from "@/lib/telegram-provider"
import { useTranslation } from "@/lib/i18n"
import { getDashboardStats } from "@/lib/api"
import Link from "next/link"

interface DashboardProps {
  onGoToProfile?: () => void;
}

export function Dashboard({ onGoToProfile }: DashboardProps) {
  const { user, webApp, isLoading } = useTelegram()
  const isReady = !isLoading
  const initData = webApp?.initData || ""
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [txTab, setTxTab] = useState<"today" | "history">("today")
  const t = useTranslation(data?.user_language || user?.language_code || "uz")

  useEffect(() => {
    if (isReady && user) {
      getDashboardStats(user.id)
        .then(resData => {
          if (resData.error) {
            console.error("Server error:", resData.error)
          } else {
            setData(resData)
          }
          setLoading(false)
        })
        .catch(err => {
          console.error("Fetch error:", err)
          setLoading(false)
        })
    }
  }, [isReady, user])

  if (!isReady || loading) {
    return (
      <div className="h-[80vh] flex items-center justify-center bg-[#F8F9FB] text-[#10B981]">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    )
  }

  // Calculate stats from data
  const dailySarf = data?.daily_expense || 0;
  const dailyLimit = data?.daily_limit || 0;
  const sarfPercent = dailyLimit > 0 ? Math.round((dailySarf / dailyLimit) * 100) : 0;

  const getProgressColor = (percent: number) => {
    if (percent < 50) return '#10B981';
    if (percent <= 100) {
      const p = (percent - 50) / 50;
      const r = Math.round(16 + (245 - 16) * p);
      const g = Math.round(185 + (158 - 185) * p);
      const b = Math.round(129 + (11 - 129) * p);
      return `rgb(${r}, ${g}, ${b})`;
    }
    if (percent <= 200) {
      const p = (percent - 100) / 100;
      const r = Math.round(245 + (239 - 245) * p);
      const g = Math.round(158 + (68 - 158) * p);
      const b = Math.round(11 + (68 - 11) * p);
      return `rgb(${r}, ${g}, ${b})`;
    }
    return '#EF4444';
  };

  const tasks = data?.tasks || [];
  const taskCount = tasks.length;

  const activeDream = data?.dreams?.[0]; // Get the first active dream
  const currentTransactions = txTab === "today" ? (data?.today_transactions || []) : (data?.history_transactions || []);

  return (
    <div className="flex flex-col bg-[#F8F9FB] text-[#1A1D1E] font-sans min-h-full">
      {/* HEADER */}
      <div className="px-4 pt-6 pb-2 flex justify-between items-center">
        <div className="flex items-center space-x-3 cursor-pointer" onClick={onGoToProfile}>
          <div className="w-12 h-12 rounded-full overflow-hidden relative">

            <img src={user?.photo_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.first_name || 'User'}&backgroundColor=000000`} alt="Avatar" className="w-full h-full object-cover rounded-full" />
          </div>
          <div>
            <div className="text-[17px] font-bold flex items-center">
              {t("Hello")}, {user?.first_name || t("User")}! <span className="ml-1 text-lg">👋</span>
            </div>
            <div className="text-[13px] text-gray-500 flex items-center mt-0.5">
              {t("Discipline Level")}: <span className="text-[#10B981] font-bold ml-1 mr-1">{data?.streak ? Math.min(100, data.streak * 10) : 0}%</span> 🔥
            </div>
          </div>
        </div>
        <div>
          <div className="flex items-center bg-white px-3 py-2 rounded-xl border border-gray-100 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
            <Calendar className="w-4 h-4 text-[#10B981] mr-2" />
            <span className="text-[12px] font-medium text-gray-700 capitalize">{new Date().toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' })}</span>
          </div>
        </div>
      </div>

      <div className="px-4 pb-6">

        {/* BUGUNGI HOLAT */}
        <div className="mt-5 mb-3">
          <h2 className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">{t("Today's Status")}</h2>
        </div>

        <div className="flex overflow-x-auto gap-3 pb-2 scrollbar-none snap-x snap-mandatory -mx-4 px-4">
          {/* Card 1: Kunlik sarf */}
          <div className="min-w-[145px] snap-center shrink-0 bg-white rounded-[20px] p-3.5 shadow-[0_4px_15px_rgba(0,0,0,0.03)] flex flex-col justify-between h-full">
            <div>
              <div className="flex items-center space-x-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-[#E8F8F3] flex items-center justify-center">
                  <Wallet className="w-4 h-4 text-[#10B981]" />
                </div>
                <span className="text-[11px] font-bold text-gray-800 leading-tight">{t("Daily Spending")}</span>
              </div>
              <div className="flex items-baseline space-x-1 flex-wrap mt-1">
                <span className="text-xl font-bold" style={{ color: getProgressColor(sarfPercent) }}>{dailySarf.toLocaleString()}</span>
                <span className="text-[11px] text-gray-500 font-medium">/ {dailyLimit.toLocaleString()} {data?.base_currency || "so'm"}</span>
              </div>
            </div>

            <div className="mt-4">
              <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden mb-1.5">
                <div className="h-full rounded-full" style={{ width: `${Math.min(100, sarfPercent)}%`, backgroundColor: getProgressColor(sarfPercent) }}></div>
              </div>
              <div className="text-[10px] font-medium" style={{ color: getProgressColor(sarfPercent) }}>{sarfPercent}% ishlatildi</div>
            </div>
          </div>

          {/* Card 2: Bugungi badal */}
          <div className="min-w-[145px] snap-center shrink-0 bg-white rounded-[20px] p-3.5 shadow-[0_4px_15px_rgba(0,0,0,0.03)] flex flex-col justify-between h-full">
            <div>
              <div className="flex items-center space-x-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-[#E8F8F3] flex items-center justify-center">
                  <Target className="w-4 h-4 text-[#10B981]" />
                </div>
                <span className="text-[11px] font-bold text-gray-800 leading-tight">{t("Today's Installment")}</span>
              </div>
              <div className="text-xl font-bold text-[#10B981] mt-1">
                {activeDream ? (activeDream.daily_limit_target || 0).toLocaleString() : "0"} <span className="text-[11px] font-medium text-gray-800 ml-0.5">{data?.base_currency || "so'm"}</span>
              </div>
            </div>

            <div className="mt-4">
              <div className="inline-block bg-[#E8F8F3] text-[#10B981] text-[9px] font-bold px-2 py-1 rounded-md">
                {t("Don't forget to pay")}
              </div>
            </div>
          </div>

          {/* Card 3: Vazifalar */}
          <div className="min-w-[145px] snap-center shrink-0 bg-white rounded-[20px] p-3.5 shadow-[0_4px_15px_rgba(0,0,0,0.03)] flex flex-col justify-between h-full">
            <div>
              <div className="flex items-center space-x-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-indigo-50 flex items-center justify-center">
                  <CheckSquare className="w-4 h-4 text-indigo-500" />
                </div>
                <span className="text-[11px] font-bold text-gray-800 leading-tight">{t("Tasks")}</span>
              </div>
              <div className="flex items-baseline space-x-1">
                <span className="text-xl font-bold text-indigo-500">{taskCount}</span>
                <span className="text-[11px] text-gray-500 font-medium"> ta</span>
              </div>
              <div className="text-[11px] text-gray-500 font-medium mt-0.5">kutilmoqda</div>
            </div>

            <div className="mt-4">
              <div className="inline-block bg-indigo-50 text-indigo-500 text-[9px] font-bold px-2 py-1 rounded-md">
                {t("Bajarishni unutmang") || "Bajarishni unutmang"}
              </div>
            </div>
          </div>
        </div>

        {/* ACTIVE DREAM CARD */}
        {activeDream && (
          <Link href="/add-goal" className="block mt-4 bg-white rounded-[24px] p-5 shadow-[0_4px_15px_rgba(0,0,0,0.03)] cursor-pointer active:scale-95 transition-transform">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-full bg-[#F4F2FF] flex items-center justify-center">
                  <Car className="w-6 h-6 text-[#7C3AED]" />
                </div>
                <div>
                  <h3 className="font-bold text-[15px] text-gray-900">{t("My Dream:")} {activeDream.title}</h3>
                  <p className="text-[11px] text-gray-500">{t("Target amount:")} {(activeDream.target || 0).toLocaleString()} {data?.base_currency || "so'm"}</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>

            <div className="mt-4 flex items-end justify-between">
              <div className="w-[80%]">
                <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden mb-3">
                  <div className="h-full bg-[#10B981] rounded-full" style={{ width: `${activeDream.progress_percent || 0}%` }}></div>
                </div>
                <div className="text-[11px] text-gray-500">{(activeDream.current || 0).toLocaleString()} {data?.base_currency || "so'm"} {t("yig'ilgan")}</div>
              </div>
              <div className="text-right">
                <div className="text-3xl font-bold text-[#10B981] mb-2 leading-none">{activeDream.progress_percent}%</div>
                <div className="flex items-center text-[11px] text-gray-500 justify-end">
                  <Calendar className="w-3 h-3 mr-1" />
                  {activeDream.daysRemaining} {t("days left")}
                </div>
              </div>
            </div>
          </Link>
        )}

        {/* BUGUNGI/BARCHA FAOLLIK */}
        <div className="mt-6 mb-3 flex justify-between items-center">
          <h2 className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">
            {txTab === "today" ? t("Today's Activity") : t("History")}
          </h2>
          <button
            onClick={() => setTxTab(txTab === "today" ? "history" : "today")}
            className="flex items-center text-[12px] font-medium text-[#10B981] transition-transform active:scale-95"
          >
            {txTab === "today" ? t("See all") : t("Today")} <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
          </button>
        </div>

        <div className="bg-white rounded-[24px] p-2 shadow-[0_4px_15px_rgba(0,0,0,0.03)]">
          <div className="divide-y divide-gray-50">

            {currentTransactions.length > 0 ? currentTransactions.map((tx: any, idx: number) => (
              <div key={tx.id || idx} className="flex items-center justify-between p-3 py-3.5">
                <div className="flex items-center space-x-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${tx.amount > 0 ? 'bg-green-50 text-[#10B981]' : 'bg-orange-50 text-orange-500'}`}>
                    <Wallet className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="font-bold text-[14px]">{tx.title}</div>
                    <div className="text-[11px] text-gray-400 font-medium">{tx.time}</div>
                  </div>
                </div>
                <div className={`font-bold text-[14px] ${tx.amount > 0 ? 'text-[#10B981]' : 'text-red-500'}`}>
                  {tx.amount > 0 ? '+' : ''}{tx.amount.toLocaleString()} {tx.currency}
                </div>
              </div>
            )) : (
              <div className="p-4 text-center text-sm text-gray-400">{t("Bugungi faollik yo'q")}</div>
            )}

          </div>
        </div>
      </div>
    </div>
  )
}
