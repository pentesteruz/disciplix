"use client"

import React, { useState, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AddGoalDrawer } from "@/components/add-goal-drawer"
import { useTelegram } from "@/lib/telegram-provider"
import { getDashboardStats, createDream, addDreamProgress, requestCancelDream, undoCancelDream, completeDreamEarly, setMainDream } from "@/lib/api"
import { 
  Car, 
  Home, 
  Plane, 
  Smartphone,
  Watch,
  Camera,
  Briefcase,
  GraduationCap,
  Gift,
  Sparkles,
  Plus,
  ArrowUp,
  XCircle,
  CheckCircle2
} from "lucide-react"

// Available Icons for selection
const ICON_MAP: Record<string, React.ElementType> = {
  car: Car, home: Home, plane: Plane, smartphone: Smartphone, laptop: Car, watch: Watch, camera: Camera, briefcase: Briefcase, gradcap: GraduationCap, gift: Gift
}

function CircularProgress({ current, target, icon: Icon, iconBg, iconColor }: {
  current: number
  target: number
  icon: React.ElementType
  iconBg: string
  iconColor: string
}) {
  const percentage = Math.min((current / target) * 100, 100)
  const circumference = 2 * Math.PI * 45
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  return (
    <div className="relative w-32 h-32">
      <svg className="w-full h-full transform -rotate-90">
        <circle
          cx="64"
          cy="64"
          r="45"
          stroke="currentColor"
          strokeWidth="8"
          fill="none"
          className="text-muted"
        />
        <circle
          cx="64"
          cy="64"
          r="45"
          stroke="currentColor"
          strokeWidth="8"
          fill="none"
          strokeLinecap="round"
          className="text-primary transition-all duration-500"
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: strokeDashoffset,
          }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <div className={`w-16 h-16 rounded-full ${iconBg} flex items-center justify-center`}>
          <Icon className={`w-8 h-8 ${iconColor}`} />
        </div>
      </div>
    </div>
  )
}

export function DreamBox({ refreshTrigger }: { refreshTrigger?: number }) {
  const { user } = useTelegram()
  const [goals, setGoals] = useState<any[]>([])
  const [isAddGoalOpen, setIsAddGoalOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [expandedGoalId, setExpandedGoalId] = useState<number | null>(null)
  const [baseCurrency, setBaseCurrency] = useState("UZS")

  const fetchGoals = () => {
    if (!user?.id) return Promise.resolve();
    setLoading(true)
    return getDashboardStats(user.id)
      .then(res => {
        setGoals(res.dreams || [])
        if (res.base_currency) setBaseCurrency(res.base_currency)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchGoals()
  }, [user, refreshTrigger])

  const featuredGoal = goals[0]
  const otherGoals = goals.slice(1)

  const handleGoalAdded = async (newGoal: any) => {
    if (!user?.id) return;
    try {
      await createDream(user.id, newGoal.title, newGoal.amount, newGoal.deadline, newGoal.daily_limit, newGoal.icon, newGoal.iconBg, newGoal.iconColor)
      await fetchGoals()
    } catch (e: any) {
      console.error("Created dream error", e)
      alert(e.message || "Maqsad qo'shishda xatolik yuz berdi")
      throw e;
    }
  }

  const handleKunlik = async (id: number, dailyTarget: number) => {
    if (!user?.id) return;
    try {
      await addDreamProgress(id, dailyTarget, true)
      fetchGoals()
    } catch (e: any) {
      alert(e.message || "Xatolik yuz berdi")
    }
  }

  const handleQoshimcha = async (id: number) => {
    if (!user?.id) return;
    const amountStr = window.prompt(`Qo'shimcha pul miqdorini kiriting (${baseCurrency}):`)
    if (!amountStr) return;
    const amount = parseFloat(amountStr)
    if (isNaN(amount) || amount <= 0) return;
    try {
      await addDreamProgress(id, amount, false)
      fetchGoals()
    } catch (e: any) {
      alert(e.message || "Xatolik")
    }
  }

  const handleYakunlash = async (id: number) => {
    if (!user?.id) return;
    try {
      await completeDreamEarly(id)
      fetchGoals()
    } catch (e: any) {
      alert(e.message || "Bekor qilindi")
    }
  }

  const handleCancel = async (id: number) => {
    if (!user?.id) return;
    try {
      await requestCancelDream(id)
      fetchGoals()
    } catch (e) {
      console.error(e)
    }
  }

  const handleUndoCancel = async (id: number) => {
    if (!user?.id) return;
    try {
      await undoCancelDream(id)
      fetchGoals()
    } catch (e: any) {
      alert(e.message || "Xatolik yuz berdi")
    }
  }

  const handleSetMain = async (id: number) => {
    if (!user?.id) return;
    try {
      await setMainDream(id)
      await fetchGoals()
      setExpandedGoalId(null)
    } catch (e: any) {
      alert(e.message || "Xatolik yuz berdi")
    }
  }

  if (loading) {
    return <div className="p-5 flex justify-center items-center h-40 text-muted-foreground animate-pulse">Yuklanmoqda...</div>
  }

  return (
    <div className="p-5 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dream Box</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Orzularingizga yetishga oz qoldi!
          </p>
        </div>
        <Button 
          size="icon" 
          variant="outline" 
          onClick={() => setIsAddGoalOpen(true)}
          className="rounded-full border-2 border-dashed border-primary/30 hover:bg-primary/5"
        >
          <Plus className="h-5 w-5 text-primary" />
        </Button>
      </div>

      {/* Featured Goal Card */}
      {featuredGoal && (
        <Card className="p-6 bg-card border-0 rounded-3xl shadow-lg">
          <div className="flex flex-col items-center text-center">
            <CircularProgress 
              current={featuredGoal.current}
              target={featuredGoal.target}
              icon={ICON_MAP[featuredGoal.icon] || Car}
              iconBg={featuredGoal.iconBg}
              iconColor={featuredGoal.iconColor}
            />
            
            <div className="mt-4">
              <h2 className="text-3xl font-bold text-foreground">
                {featuredGoal.current.toLocaleString()} {baseCurrency}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                / {featuredGoal.target.toLocaleString()} {baseCurrency}
              </p>
            </div>

            {/* AI Forecast Badge */}
            <div className="flex items-center gap-1.5 mt-4 px-4 py-2 bg-primary/10 rounded-full">
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium text-primary">
                {featuredGoal.daysRemaining} kunda erishasiz
              </span>
            </div>

            {/* Custom Action Buttons (Kunlik qo'shish, Bekor qilish, Yakunlash) */}
            {featuredGoal.cancel_requested ? (
              <div className="mt-6 w-full bg-orange-50/50 border border-orange-200 p-4 rounded-2xl text-center">
                <p className="text-sm text-orange-700 font-medium mb-3 leading-tight">
                  Siz orzudan voz kechdingiz. Yana bir bor o'ylab ko'ring, hali tasdiqlanguncha vaqtingiz bor!
                </p>
                <Button 
                  onClick={() => handleUndoCancel(featuredGoal.id)}
                  variant="outline" 
                  className="w-full rounded-xl border-orange-200 text-orange-700 hover:bg-orange-100 h-11"
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  Orzuni qaytarish (Bekor qilish)
                </Button>
              </div>
            ) : (
              <div className="flex flex-col gap-3 mt-6 w-full">
                {/* Top Row: Add and Finish */}
                <div className="flex gap-3 w-full">
                  <Button 
                    onClick={() => handleKunlik(featuredGoal.id, featuredGoal.daily_limit_target)}
                    variant="outline" 
                    className="flex-1 rounded-2xl border-primary text-primary hover:bg-primary/5 h-12"
                  >
                    <ArrowUp className="h-4 w-4 mr-2" />
                    Kunlik qo'shish
                  </Button>
                  
                  {featuredGoal.current >= featuredGoal.target ? (
                    <Button 
                      onClick={() => handleYakunlash(featuredGoal.id)}
                      variant="default" 
                      className="flex-1 rounded-2xl bg-primary text-primary-foreground hover:bg-primary/90 h-12"
                    >
                      <CheckCircle2 className="h-4 w-4 mr-2" />
                      Yakunlash
                    </Button>
                  ) : (
                    <Button 
                      onClick={() => handleQoshimcha(featuredGoal.id)}
                      variant="default" 
                      className="flex-1 rounded-2xl bg-primary text-primary-foreground hover:bg-primary/90 h-12"
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Qo'shimcha pul
                    </Button>
                  )}
                </div>
                
                {/* Bottom Row: Cancel */}
                <Button 
                  onClick={() => handleCancel(featuredGoal.id)}
                  variant="outline" 
                  className="w-full rounded-2xl border-destructive/30 text-destructive hover:bg-destructive/10 h-12"
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  Bekor qilish
                </Button>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Other Goals */}
      {otherGoals.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-semibold text-foreground">Boshqa maqsadlar</h2>
          
          {otherGoals.map((goal) => {
            const percentage = Math.round((goal.current / goal.target) * 100)
            const isExpanded = expandedGoalId === goal.id
            
            return (
              <div key={goal.id} className="space-y-2">
                <Card 
                  onClick={() => setExpandedGoalId(isExpanded ? null : goal.id)}
                  className={`p-4 bg-card border-0 rounded-2xl shadow-sm active:scale-[0.98] transition-all cursor-pointer ${isExpanded ? 'ring-2 ring-primary/50' : ''}`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-2xl ${goal.iconBg} flex items-center justify-center flex-shrink-0`}>
                      {ICON_MAP[goal.icon] && React.createElement(ICON_MAP[goal.icon], { className: `h-6 w-6 ${goal.iconColor}` })}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="font-medium text-foreground">{goal.title}</p>
                        <p className="text-sm font-semibold text-primary">{percentage}%</p>
                      </div>
                      
                      <div className="flex items-center justify-between mt-1">
                        <p className="text-sm text-muted-foreground">
                          {goal.current.toLocaleString()} / {goal.target.toLocaleString()} {baseCurrency}
                        </p>
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Sparkles className="h-3 w-3" />
                          {goal.daysRemaining} kun
                        </p>
                      </div>
                      
                      {/* Mini progress bar */}
                      <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-2">
                        <div 
                          className="h-full rounded-full bg-primary transition-all duration-500"
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </Card>

                {/* Expanded Action Menu */}
                {isExpanded && (
                  <div className="flex flex-col gap-2 px-1 pt-1 animate-in slide-in-from-top-2 duration-200">
                    <div className="flex gap-2">
                      <Button 
                        onClick={() => handleSetMain(goal.id)}
                        variant="default" 
                        size="sm"
                        className="flex-1 bg-primary border-0 rounded-xl"
                      >
                        <ArrowUp className="h-4 w-4 mr-1.5" />
                        Asosiyga
                      </Button>
                      <Button 
                        onClick={() => handleKunlik(goal.id, goal.daily_limit_target)}
                        variant="outline" 
                        size="sm"
                        className="flex-1 border-primary text-primary rounded-xl"
                      >
                        <Plus className="h-4 w-4 mr-1.5" />
                        Kunlik
                      </Button>
                    </div>
                    <div className="flex gap-2">
                      <Button 
                        onClick={() => handleQoshimcha(goal.id)}
                        variant="outline" 
                        size="sm"
                        className="flex-1 rounded-xl"
                      >
                        <Plus className="h-4 w-4 mr-1.5" />
                        Qo'shimcha
                      </Button>
                      <Button 
                        onClick={() => handleCancel(goal.id)}
                        variant="destructive" 
                        size="sm"
                        className="flex-1 rounded-xl"
                      >
                        <XCircle className="h-4 w-4 mr-1.5" />
                        O'chirish
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Add New Goal Button */}
      <Card 
        className="p-4 border-2 border-dashed border-primary/20 rounded-2xl bg-primary/5 cursor-pointer hover:bg-primary/10 transition-colors"
        onClick={() => setIsAddGoalOpen(true)}
      >
        <div className="flex items-center justify-center gap-2 text-primary">
          <Plus className="h-5 w-5" />
          <span className="font-medium">Yangi maqsad qo'shish</span>
        </div>
      </Card>

      {/* Goal Add Drawer */}
      <AddGoalDrawer 
        isOpen={isAddGoalOpen} 
        onClose={() => setIsAddGoalOpen(false)} 
        onGoalAdded={handleGoalAdded}
      />
    </div>
  )
}
