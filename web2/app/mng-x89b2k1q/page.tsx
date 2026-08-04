"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useTelegram } from "@/lib/telegram-provider"
import {
  getAdminDashboard,
  getAdminFinance,
  getAdminSettings,
  updateAdminSettings,
  getAdminPromos,
  createAdminPromo,
  deleteAdminPromo,
  searchAdminUser,
  toggleAdminFreeze,
  archiveAdminUser,
  confirmAdminDreamCancel,
  broadcastAdminMessage,
  getAdminReferralsStats,
  getAdminUserReferrals,
  getAdminCancelRequests,
  requestUserHardDelete,
} from "@/lib/api"
import {
  LayoutDashboard, Users, CircleDollarSign, Target, Activity, Settings, ShieldAlert,
  Bell, LogOut, CheckCircle2, AlertTriangle, TrendingUp, Search, Radio
} from "lucide-react"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar
} from "recharts"

function formatNumber(num: number): string {
  if (!num) return "0"
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ")
}

export default function AdminPage() {
  const { user } = useTelegram()
  const [activeTab, setActiveTab] = useState("dashboard")
  
  const [dashboard, setDashboard] = useState<any>(null)
  const [finance, setFinance] = useState<any>(null)
  const [settings, setSettings] = useState<any>({})
  const [promos, setPromos] = useState<any[]>([])
  const [refStats, setRefStats] = useState<any>(null)
  const [modRequests, setModRequests] = useState<any[]>([])

  const [searchId, setSearchId] = useState("")
  const [userResult, setUserResult] = useState<any>(null)
  const [referrals, setReferrals] = useState<number[]>([])
  const [refPage, setRefPage] = useState(1)
  const [refHasMore, setRefHasMore] = useState(false)

  const [promoCode, setPromoCode] = useState("")
  const [promoDays, setPromoDays] = useState("")
  const [promoUses, setPromoUses] = useState("")

  const [adminUsernames, setAdminUsernames] = useState("")
  const [trialPremiumDays, setTrialPremiumDays] = useState("3")
  const [broadcastMsg, setBroadcastMsg] = useState("")
  const [status, setStatus] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [dash, fin, settingsRes, promosRes, refRes, modRes] = await Promise.all([
          getAdminDashboard(),
          getAdminFinance(),
          getAdminSettings(),
          getAdminPromos(),
          getAdminReferralsStats(),
          getAdminCancelRequests().catch(() => ({ requests: [] }))
        ])
        setDashboard(dash)
        setFinance(fin)
        setSettings(settingsRes || {})
        setAdminUsernames(settingsRes?.admin_usernames || "")
        setTrialPremiumDays(settingsRes?.trial_premium_days || "3")
        setPromos(promosRes || [])
        setRefStats(refRes || null)
        setModRequests(modRes?.requests || [])
      } catch (e: any) {
        setStatus(e?.message || "Ma'lumotlar yuklanishida xatolik")
      }
    }
    load()
  }, [])

  const handleSearch = async () => {
    if (!searchId.trim()) return
    setStatus(null)
    try {
      const res = await searchAdminUser(searchId.trim())
      setUserResult(res)
      setReferrals([])
      setRefPage(1)
      const refs = await getAdminUserReferrals(searchId.trim(), 1)
      setReferrals(refs.referrals || [])
      setRefHasMore(Boolean(refs.has_more))
    } catch (e: any) {
      setStatus(e?.message || "Foydalanuvchi topilmadi")
    }
  }

  const handleToggleFreeze = async () => {
    if (!userResult?.telegram_id) return
    const res = await toggleAdminFreeze(userResult.telegram_id)
    setUserResult({ ...userResult, is_frozen: res.is_frozen })
  }

  const handleArchive = async () => {
    if (!userResult?.telegram_id) return
    await requestUserHardDelete(userResult.telegram_id)
    setStatus("Foydalanuvchiga o'chirish so'rovi yuborildi")
  }

  const handleConfirmCancel = async (userId?: number, dreamId?: number) => {
    const tId = userId || userResult?.telegram_id
    const dId = dreamId || userResult?.active_dream_id
    if (!tId || !dId) return
    await confirmAdminDreamCancel(tId, dId)
    if (userId) {
       setModRequests(prev => prev.filter(req => req.user_id !== userId))
    } else {
       setUserResult({ ...userResult, dream_cancel_requested: false })
    }
  }

  const loadMoreRefs = async () => {
    if (!userResult?.telegram_id) return
    const nextPage = refPage + 1
    const refs = await getAdminUserReferrals(userResult.telegram_id, nextPage)
    setReferrals((prev) => [...prev, ...(refs.referrals || [])])
    setRefHasMore(Boolean(refs.has_more))
    setRefPage(nextPage)
  }

  const handleSaveSettings = async () => {
    await updateAdminSettings({ admin_usernames: adminUsernames, trial_premium_days: trialPremiumDays })
    setStatus("Sozlamalar saqlandi")
  }

  const handleCreatePromo = async () => {
    if (!promoCode || !promoDays) return
    await createAdminPromo(promoCode, Number(promoDays), Number(promoUses || 1))
    const promosRes = await getAdminPromos()
    setPromos(promosRes || [])
    setPromoCode("")
    setPromoDays("")
    setPromoUses("")
  }

  const handleDeletePromo = async (id: number) => {
    await deleteAdminPromo(id)
    const promosRes = await getAdminPromos()
    setPromos(promosRes || [])
  }

  const handleBroadcast = async () => {
    if (!broadcastMsg.trim()) return
    const res = await broadcastAdminMessage(broadcastMsg.trim())
    setStatus(`Yuborildi: ${res.delivered_to || 0}`)
    setBroadcastMsg("")
  }

  const menuItems = [
    { id: "dashboard", icon: LayoutDashboard, label: "Dashboard" },
    { id: "users", icon: Users, label: "Users" },
    { id: "finance", icon: CircleDollarSign, label: "Finance" },
    { id: "moderation", icon: ShieldAlert, label: "Moderation" },
    { id: "broadcast", icon: Radio, label: "Broadcast" },
    { id: "promos", icon: CircleDollarSign, label: "Promo Codes" },
    { id: "settings", icon: Settings, label: "Settings" }
  ]

  return (
    <div className="flex h-screen bg-[#F8F9FB] text-slate-900 font-sans">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-slate-200 flex flex-col justify-between">
        <div>
          <div className="h-16 flex items-center px-6 border-b border-slate-100">
            <div className="flex items-center gap-2 text-primary">
              <ShieldAlert className="w-6 h-6" />
              <span className="font-bold text-lg tracking-tight">Disciplix Admin</span>
            </div>
          </div>
          <div className="p-4 space-y-1">
            {menuItems.map(item => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === item.id 
                    ? "bg-primary/10 text-primary" 
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <item.icon className="w-4 h-4" />
                {item.label}
              </button>
            ))}
          </div>
        </div>
        
        <div className="p-4 border-t border-slate-100">
          <div className="flex items-center gap-3 px-4 py-3 bg-slate-50 rounded-lg border border-slate-100">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold text-xs">
              AD
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-900 truncate">Super Admin</p>
              <p className="text-xs text-slate-500 truncate">ID: {user?.id || "-"}</p>
            </div>
            <LogOut className="w-4 h-4 text-slate-400 cursor-pointer hover:text-red-500" />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8">
          <h1 className="text-xl font-bold text-slate-800 capitalize">{activeTab.replace("_", " ")}</h1>
          <div className="flex items-center gap-4">
            <div className="text-sm text-slate-500 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              {status || "Tizim faol"}
            </div>
            <button className="relative p-2 text-slate-400 hover:text-slate-600">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-red-500"></span>
            </button>
          </div>
        </header>

        {/* Scrollable Area */}
        <main className="flex-1 overflow-auto p-8">
          
          {activeTab === "dashboard" && dashboard && (
            <div className="space-y-6">
              {/* KPI Cards */}
              <div className="grid grid-cols-4 gap-4">
                <Card className="p-5 flex flex-col justify-between border-slate-200 shadow-sm">
                  <p className="text-sm font-medium text-slate-500">Jami foydalanuvchilar</p>
                  <p className="text-3xl font-bold text-slate-900 mt-2">{formatNumber(dashboard.stats?.total_users)}</p>
                  <p className="text-xs font-medium text-green-600 mt-2 flex items-center gap-1">
                    <TrendingUp className="w-3 h-3" /> +{formatNumber(dashboard.stats?.new_users_today)} bugun
                  </p>
                </Card>
                <Card className="p-5 flex flex-col justify-between border-slate-200 shadow-sm">
                  <p className="text-sm font-medium text-slate-500">Faol (Bugun)</p>
                  <p className="text-3xl font-bold text-slate-900 mt-2">{formatNumber(dashboard.stats?.active_users_today)}</p>
                </Card>
                <Card className="p-5 flex flex-col justify-between border-slate-200 shadow-sm">
                  <p className="text-sm font-medium text-slate-500">Premium foydalanuvchilar</p>
                  <p className="text-3xl font-bold text-slate-900 mt-2">{formatNumber(dashboard.stats?.total_premium)}</p>
                </Card>
                <Card className="p-5 flex flex-col justify-between border-slate-200 shadow-sm">
                  <p className="text-sm font-medium text-slate-500">Bugungi tushum</p>
                  <p className="text-3xl font-bold text-green-600 mt-2">{formatNumber(dashboard.stats?.today_revenue)}</p>
                  <p className="text-xs text-slate-400 mt-2">so'm</p>
                </Card>
                <Card className="p-5 flex flex-col justify-between border-slate-200 shadow-sm">
                  <p className="text-sm font-medium text-slate-500">Bugun yaratilgan orzular</p>
                  <p className="text-3xl font-bold text-slate-900 mt-2">{formatNumber(dashboard.stats?.dreams_today)}</p>
                </Card>
                <Card className="p-5 flex flex-col justify-between border-slate-200 shadow-sm">
                  <p className="text-sm font-medium text-slate-500">Bugun bajarilgan vazifalar</p>
                  <p className="text-3xl font-bold text-slate-900 mt-2">{formatNumber(dashboard.stats?.tasks_completed_today)}</p>
                </Card>
                <Card className="p-5 flex flex-col justify-between border-slate-200 shadow-sm">
                  <p className="text-sm font-medium text-slate-500">O'rtacha intizom balli</p>
                  <p className="text-3xl font-bold text-primary mt-2">{dashboard.stats?.avg_discipline}%</p>
                </Card>
                <Card className="p-5 flex flex-col justify-between border-slate-200 shadow-sm">
                  <p className="text-sm font-medium text-slate-500">Xatoliklar (bugun)</p>
                  <p className="text-3xl font-bold text-red-500 mt-2">{dashboard.stats?.errors_today}</p>
                </Card>
              </div>

              {/* Charts Row 1 */}
              <div className="grid grid-cols-3 gap-6">
                <Card className="col-span-2 p-5 shadow-sm border-slate-200">
                  <h3 className="text-base font-semibold text-slate-900 mb-6">Tushum statistikasi (7 kun)</h3>
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={dashboard.revenue_chart || []}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 12}} dy={10} />
                        <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 12}} width={60} 
                               tickFormatter={(value) => `${value / 1000}k`} />
                        <RechartsTooltip 
                          contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                          formatter={(value: number) => [`${formatNumber(value)} so'm`, 'Tushum']}
                        />
                        <Line type="monotone" dataKey="amount" stroke="#10B981" strokeWidth={3} dot={{r: 4, fill: '#10B981', strokeWidth: 2, stroke: '#fff'}} activeDot={{r: 6}} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
                
                <Card className="p-5 shadow-sm border-slate-200 flex flex-col items-center justify-center relative">
                  <h3 className="text-base font-semibold text-slate-900 mb-2 w-full text-left absolute top-5 left-5">Platform Health</h3>
                  <div className="w-40 h-40 relative mt-8">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={[
                            { value: dashboard.health?.score || 0, fill: "#10B981" },
                            { value: 100 - (dashboard.health?.score || 0), fill: "#E2E8F0" }
                          ]}
                          innerRadius={60}
                          outerRadius={80}
                          dataKey="value"
                          startAngle={90}
                          endAngle={-270}
                          stroke="none"
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-3xl font-bold text-slate-900">{dashboard.health?.score || 0}%</span>
                      <span className="text-xs text-slate-500 font-medium mt-1">Sog'lom</span>
                    </div>
                  </div>
                  <div className="w-full mt-6 space-y-2 text-xs">
                     <div className="flex justify-between items-center"><span className="text-slate-500 flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-green-500"></div>Faol foydalanuvchilar</span><span className="font-semibold">{dashboard.health?.metrics?.active_users}%</span></div>
                     <div className="flex justify-between items-center"><span className="text-slate-500 flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-green-500"></div>Vazifa bajarish</span><span className="font-semibold">{dashboard.health?.metrics?.task_completion}%</span></div>
                     <div className="flex justify-between items-center"><span className="text-slate-500 flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-green-500"></div>Premium konversiya</span><span className="font-semibold">{dashboard.health?.metrics?.premium_conversion}%</span></div>
                  </div>
                </Card>
              </div>

              {/* Charts Row 2 */}
              <div className="grid grid-cols-3 gap-6">
                <Card className="p-5 shadow-sm border-slate-200">
                   <h3 className="text-base font-semibold text-slate-900 mb-6">Eng mashhur orzular</h3>
                   <div className="h-48 w-full flex">
                      <div className="w-1/2 h-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={dashboard.popular_dreams || []}
                              innerRadius={40}
                              outerRadius={70}
                              dataKey="value"
                              stroke="none"
                            >
                              {(dashboard.popular_dreams || []).map((entry: any, index: number) => (
                                <Cell key={`cell-${index}`} fill={entry.fill} />
                              ))}
                            </Pie>
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="w-1/2 flex flex-col justify-center space-y-3">
                         {(dashboard.popular_dreams || []).map((entry: any, index: number) => (
                            <div key={index} className="flex justify-between items-center text-xs">
                               <div className="flex items-center gap-2">
                                 <div className="w-2 h-2 rounded-full" style={{backgroundColor: entry.fill}}></div>
                                 <span className="text-slate-600">{entry.name}</span>
                               </div>
                               <span className="font-bold">{entry.value}%</span>
                            </div>
                         ))}
                      </div>
                   </div>
                </Card>

                <Card className="col-span-2 p-5 shadow-sm border-slate-200">
                  <h3 className="text-base font-semibold text-slate-900 mb-6">Foydalanuvchi faolligi (7 kun)</h3>
                  <div className="h-48 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={dashboard.user_activity || []}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 12}} dy={10} />
                        <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 12}} width={40} />
                        <RechartsTooltip cursor={{fill: '#F1F5F9'}} contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                        <Bar dataKey="count" fill="#10B981" radius={[4, 4, 0, 0]} maxBarSize={40} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
              </div>
            </div>
          )}

          {activeTab === "users" && (
            <div className="space-y-6">
              <Card className="p-6 space-y-4 shadow-sm border-slate-200">
                <h3 className="text-lg font-semibold text-slate-900">Foydalanuvchi qidirish</h3>
                <div className="flex gap-3 max-w-xl">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <Input 
                      value={searchId} 
                      onChange={(e) => setSearchId(e.target.value)} 
                      placeholder="Telegram ID yoki Ism..." 
                      className="pl-9 h-11"
                    />
                  </div>
                  <Button onClick={handleSearch} className="h-11 px-6">Izlash</Button>
                </div>
              </Card>

              {userResult && (
                <div className="grid grid-cols-3 gap-6">
                  <Card className="col-span-2 p-6 space-y-6 shadow-sm border-slate-200">
                    <div className="flex items-start justify-between">
                      <div>
                        <h2 className="text-2xl font-bold text-slate-900">{userResult.name}</h2>
                        <p className="text-slate-500">ID: {userResult.telegram_id}</p>
                      </div>
                      <div className={`px-3 py-1 rounded-full text-xs font-semibold ${userResult.is_premium ? 'bg-primary/10 text-primary' : 'bg-slate-100 text-slate-600'}`}>
                        {userResult.is_premium ? "Premium" : "Oddiy"}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-y-4 gap-x-8 text-sm">
                       <div><p className="text-slate-500 mb-1">Holat</p><p className="font-semibold text-slate-900">{userResult.is_frozen ? <span className="text-red-500">Muzlatilgan</span> : <span className="text-green-500">Aktiv</span>}</p></div>
                       <div><p className="text-slate-500 mb-1">Intizom</p><p className="font-semibold text-slate-900">{userResult.discipline_score || 0}%</p></div>
                       <div><p className="text-slate-500 mb-1">Balans</p><p className="font-semibold text-slate-900">{formatNumber(userResult.balance || 0)} so'm</p></div>
                       <div><p className="text-slate-500 mb-1">Oxirgi faollik</p><p className="font-semibold text-slate-900">{userResult.last_active || "Noma'lum"}</p></div>
                    </div>

                    <div className="flex gap-3 pt-4 border-t border-slate-100">
                      <Button onClick={handleToggleFreeze} variant={userResult.is_frozen ? "outline" : "secondary"}>
                        {userResult.is_frozen ? "Muzlatishni bekor qilish" : "Muzlatib qo'yish"}
                      </Button>
                      <Button onClick={handleArchive} variant="destructive">
                        Arxivlash (O'chirish)
                      </Button>
                    </div>
                  </Card>

                  <Card className="p-6 shadow-sm border-slate-200">
                    <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2"><Users className="w-4 h-4"/> Referallar</h3>
                    {referrals.length === 0 ? (
                      <p className="text-sm text-slate-500">Referallar yo'q</p>
                    ) : (
                      <div className="space-y-3">
                        {referrals.map((ref) => (
                          <div key={ref} className="text-sm p-3 border border-slate-100 rounded-lg bg-slate-50">
                            ID: {ref}
                          </div>
                        ))}
                      </div>
                    )}
                    {refHasMore && (
                      <Button variant="outline" className="w-full mt-4" onClick={loadMoreRefs}>Yana yuklash</Button>
                    )}
                  </Card>
                </div>
              )}
            </div>
          )}

          {activeTab === "finance" && finance && (
             <div className="space-y-6">
                <div className="grid grid-cols-3 gap-6">
                  <Card className="p-6 shadow-sm border-slate-200 flex flex-col justify-center items-center text-center">
                     <p className="text-slate-500 font-medium mb-2">Umumiy Tushum (Premium)</p>
                     <p className="text-4xl font-bold text-green-600">{formatNumber(finance.total_income || 0)} <span className="text-xl text-slate-400">so'm</span></p>
                  </Card>
                  <Card className="p-6 shadow-sm border-slate-200 flex flex-col justify-center items-center text-center">
                     <p className="text-slate-500 font-medium mb-2">Oylik Daromad</p>
                     <p className="text-3xl font-bold text-blue-600">{formatNumber(finance.monthly_income || 0)} <span className="text-lg text-slate-400">so'm</span></p>
                  </Card>
                  <Card className="p-6 shadow-sm border-slate-200 flex flex-col justify-center items-center text-center">
                     <p className="text-slate-500 font-medium mb-2">Konversiya darajasi</p>
                     <p className="text-3xl font-bold text-purple-600">{(finance.conversion_rate || 0).toFixed(2)}%</p>
                  </Card>
                </div>
             </div>
          )}



          {activeTab === "moderation" && (
             <div className="space-y-6">
                <Card className="p-6 shadow-sm border-slate-200">
                   <h3 className="font-semibold text-slate-900 mb-4">Orzu bekor qilish so'rovlari</h3>
                   {modRequests.length === 0 ? (
                      <p className="text-sm text-slate-500">Hozircha so'rovlar yo'q.</p>
                   ) : (
                      <div className="space-y-4">
                         {modRequests.map(req => (
                            <div key={req.user_id} className="border border-red-200 rounded-lg p-4 flex justify-between items-center bg-red-50/50">
                               <div>
                                  <p className="font-bold text-slate-900">{req.first_name} <span className="text-slate-500 font-normal text-xs">(ID: {req.user_id})</span></p>
                                  <p className="text-sm mt-1">Orzusi: <span className="font-medium">{req.dream_name}</span></p>
                                  <p className="text-xs text-slate-500 mt-1">Yig'ilgan: {formatNumber(req.saved)} / {formatNumber(req.total)} so'm</p>
                               </div>
                               <Button variant="destructive" onClick={() => handleConfirmCancel(req.user_id, req.dream_id)}>Tasdiqlash (O'chirish)</Button>
                            </div>
                         ))}
                      </div>
                   )}
                </Card>
             </div>
          )}

          {activeTab === "promos" && (
             <div className="space-y-6 max-w-4xl">
               <Card className="p-6 shadow-sm border-slate-200">
                  <h3 className="text-lg font-semibold text-slate-900 mb-4">Yangi promokod yaratish</h3>
                  <div className="flex gap-4 items-end">
                    <div className="flex-1 space-y-2">
                       <Label>Promokod matni</Label>
                       <Input value={promoCode} onChange={(e) => setPromoCode(e.target.value)} placeholder="Masalan: DISIPLINA20" />
                    </div>
                    <div className="w-32 space-y-2">
                       <Label>Premium kuni</Label>
                       <Input value={promoDays} type="number" onChange={(e) => setPromoDays(e.target.value)} placeholder="30" />
                    </div>
                    <div className="w-32 space-y-2">
                       <Label>Foydalanish limiti</Label>
                       <Input value={promoUses} type="number" onChange={(e) => setPromoUses(e.target.value)} placeholder="100" />
                    </div>
                    <Button onClick={handleCreatePromo} className="h-10">Yaratish</Button>
                  </div>
               </Card>

               <Card className="p-6 shadow-sm border-slate-200">
                  <h3 className="text-lg font-semibold text-slate-900 mb-4">Faol promokodlar</h3>
                  {promos.length === 0 ? (
                     <p className="text-slate-500 text-sm">Faol promokodlar yo'q</p>
                  ) : (
                     <div className="space-y-3">
                        {promos.map(p => (
                           <div key={p.id} className="flex items-center justify-between p-4 bg-slate-50 border border-slate-100 rounded-lg">
                              <div>
                                 <p className="font-bold text-slate-900 text-lg tracking-wide">{p.code}</p>
                                 <p className="text-sm text-slate-500">{p.days} kunlik premium • Ishlatildi: {p.current_uses} / {p.max_uses}</p>
                              </div>
                              <Button variant="destructive" size="sm" onClick={() => handleDeletePromo(p.id)}>O'chirish</Button>
                           </div>
                        ))}
                     </div>
                  )}
               </Card>
             </div>
          )}

          {activeTab === "broadcast" && (
             <div className="max-w-2xl">
               <Card className="p-6 shadow-sm border-slate-200 space-y-4">
                  <h3 className="text-lg font-semibold text-slate-900">Ommaviy e'lon (Broadcast)</h3>
                  <div className="space-y-2">
                     <Label>Xabar matni</Label>
                     <textarea 
                        className="w-full min-h-[150px] p-3 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm"
                        placeholder="Barcha foydalanuvchilarga yuboriladigan xabar..."
                        value={broadcastMsg}
                        onChange={(e) => setBroadcastMsg(e.target.value)}
                     ></textarea>
                  </div>
                  <Button onClick={handleBroadcast} className="w-full">Yuborish</Button>
               </Card>
             </div>
          )}

          {activeTab === "settings" && (
             <div className="max-w-2xl space-y-6">
               <Card className="p-6 shadow-sm border-slate-200 space-y-4">
                  <h3 className="text-lg font-semibold text-slate-900">Tizim sozlamalari</h3>
                  <div className="space-y-4">
                     <div className="space-y-2">
                        <Label>Admin username'lar (vergul bilan)</Label>
                        <Input 
                           value={adminUsernames} 
                           onChange={(e) => setAdminUsernames(e.target.value)} 
                           placeholder="@admin1, @admin2" 
                        />
                     </div>
                     <div className="space-y-2">
                        <Label>Yangi foydalanuvchilarga bepul Premium (kun)</Label>
                        <Input 
                           type="number"
                           value={trialPremiumDays} 
                           onChange={(e) => setTrialPremiumDays(e.target.value)} 
                           placeholder="3" 
                        />
                     </div>
                     <Button onClick={handleSaveSettings}>Saqlash</Button>
                  </div>
               </Card>
             </div>
          )}



        </main>
      </div>
    </div>
  )
}
