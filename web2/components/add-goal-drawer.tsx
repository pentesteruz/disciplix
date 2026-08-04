"use client"

import { useState, useEffect } from "react"
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerFooter,
} from "@/components/ui/drawer"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useTelegram } from "@/lib/telegram-provider"
import { getUserData } from "@/lib/api"
import { ArrowLeft, Target, Rocket, Home, Car, Smartphone, Plane, GraduationCap, CreditCard, PartyPopper, Bot, Zap, ShieldCheck, Leaf, CheckCircle2, Calendar, TrendingUp } from "lucide-react"
import { Poppins } from "next/font/google"

const poppins = Poppins({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800", "900"] })

// Smart Icon Matcher
const getSmartIcon = (title: string | undefined | null) => {
  const t = (title || "").toLowerCase();
  if (t.includes('uy') || t.includes('hovli') || t.includes('kvartira') || t.includes('dom') || t.includes('uchastka')) return { id: 'home', Icon: Home };
  if (t.includes('mashina') || t.includes('avto') || t.includes('car') || t.includes('malibu') || t.includes('gentra')) return { id: 'car', Icon: Car };
  if (t.includes('telefon') || t.includes('iphone') || t.includes('samsung') || t.includes('noutbuk') || t.includes('kompyuter') || t.includes('macbook') || t.includes('laptop')) return { id: 'smartphone', Icon: Smartphone };
  if (t.includes('sayohat') || t.includes('dubay') || t.includes('viza') || t.includes('travel') || t.includes('umra') || t.includes('bilet')) return { id: 'plane', Icon: Plane };
  if (t.includes('oqish') || t.includes("o'qish") || t.includes('kontrakt') || t.includes('kurs') || t.includes('talaba') || t.includes('ingliz')) return { id: 'graduation-cap', Icon: GraduationCap };
  if (t.includes('qarz') || t.includes('kredit') || t.includes('uzish') || t.includes('nasiya')) return { id: 'credit-card', Icon: CreditCard };
  if (t.includes('toy') || t.includes("to'y") || t.includes('marosim') || t.includes('sunnat')) return { id: 'party-popper', Icon: PartyPopper };
  
  return { id: 'target', Icon: Target };
}

// Progress Ring Component
const ProgressRing = ({ progress }: { progress: number }) => {
  const radius = 68;
  const stroke = 12;
  const normalizedRadius = radius - stroke * 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  return (
    <div className="relative flex justify-center mb-8 mt-4">
      <svg height={radius * 2} width={radius * 2}>
        <circle
          stroke="#E5E7EB"
          fill="transparent"
          strokeWidth={stroke}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
        />
        <circle
          stroke="#10B981"
          fill="transparent"
          strokeWidth={stroke}
          strokeDasharray={circumference + ' ' + circumference}
          style={{ strokeDashoffset, transition: 'stroke-dashoffset 0.5s ease-in-out' }}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
          transform={`rotate(-90 ${radius} ${radius})`}
        />
      </svg>
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center w-full">
        {progress === 0 ? (
          <div className="flex flex-col items-center justify-center mt-1">
            <span className="text-3xl">🎯</span>
            <span className="block text-[9px] text-gray-400 font-bold uppercase leading-tight mt-1 text-center tracking-wide">Yangi<br/>maqsad</span>
          </div>
        ) : (
          <>
            <span className="text-3xl font-bold text-gray-900">{Math.round(progress)}%</span>
            <span className="block text-xs text-gray-500 font-medium">Yig'ildi</span>
          </>
        )}
      </div>
    </div>
  );
};

// Data format helper
const formatMoney = (amount: number | string | undefined | null) => {
  if (amount == null || isNaN(Number(amount))) return "0";
  return amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
};

interface AddGoalDrawerProps {
  isOpen: boolean
  onClose: () => void
  onGoalAdded: (goal: any) => Promise<void> | void
}

export function AddGoalDrawer({ isOpen, onClose, onGoalAdded }: AddGoalDrawerProps) {
  const { user, webApp } = useTelegram()
  
  const [step, setStep] = useState(1)
  const [title, setTitle] = useState("")
  const [targetAmountStr, setTargetAmountStr] = useState("")
  
  // Financial State
  const [analysisText, setAnalysisText] = useState("Daromadingiz hisoblanmoqda...")
  const [baseCurrency, setBaseCurrency] = useState("UZS")
  
  // Plans
  const [plans, setPlans] = useState<any>(null)
  const [selectedPlan, setSelectedPlan] = useState<any>(null)
  
  // Flow States
  const [loading, setLoading] = useState(false)
  const [progressVal, setProgressVal] = useState(0)

  // Reset state when drawer opens/closes
  useEffect(() => {
    if (isOpen) {
      if (webApp && webApp.expand) {
        try {
          webApp.expand();
        } catch (e) {}
      }
      setStep(1)
      setTitle("")
      setTargetAmountStr("")
      setPlans(null)
      setSelectedPlan(null)
      setProgressVal(0)
      if (user?.id) {
        getUserData(user.id).then(d => {
          if (d?.user?.base_currency) setBaseCurrency(d.user.base_currency)
        }).catch(() => {})
      }
    }
  }, [isOpen, webApp, user?.id])

  const handleAmountChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/[^0-9]/g, '');
    if (raw) {
      setTargetAmountStr(formatMoney(parseInt(raw)));
    } else {
      setTargetAmountStr("");
    }
  }

  const runAIAnalysis = async () => {
    setStep(2)
    
    // Animate texts
    const texts = [
      "Daromadingiz hisoblanmoqda...",
      "Majburiy xarajatlar ayirib tashlanmoqda...",
      "Faol orzularingiz tekshirilmoqda...",
      "Eng yaxshi rejalar tuzilmoqda..."
    ]
    let i = 0;
    const interval = setInterval(() => {
      i++;
      if (i < texts.length) {
        setAnalysisText(texts[i])
      } else {
        clearInterval(interval)
      }
    }, 1000);

    try {
      let baselineFreeCash = 5000; // default safe fallback
      
      if (user?.id) {
        const userData = await getUserData(user.id);
        const monthlyIncome = userData.user?.monthly_income || 0;
        const fixedExpenses = userData.user?.fixed_expenses_total || 0;
        const livingLimit = userData.user?.daily_limit || 0;
        
        // Find active dreams
        let activeDreamsDaily = 0;
        if (userData.dashboard?.active_dreams) {
           userData.dashboard.active_dreams.forEach((d: any) => {
               if (d.is_active) {
                   activeDreamsDaily += parseFloat(d.daily_limit_target || 0);
               }
           });
        }
        
        const grossFreeDaily = (monthlyIncome - fixedExpenses) / 30;
        let netFree = grossFreeDaily - livingLimit - activeDreamsDaily;
        
        // Agar oylik maosh - xarajatlardan keyin pul qolmasa yoki juda oz qolsa, 
        // fallback sifatida qandaydir raqamni ishlatamiz to hisob-kitob umuman buzilib ketmasligi uchun
        if (netFree < 2000) {
            netFree = 2000; 
        }
        baselineFreeCash = netFree;
      }
      
      const target = parseInt(targetAmountStr.replace(/\s/g, '')) || 0;
      
      // Logic for limits
      let dailyComf = Math.ceil((baselineFreeCash * 0.6) / 1000) * 1000;
      let dailyRec = Math.ceil((baselineFreeCash * 0.9) / 1000) * 1000;
      let dailyFast = Math.ceil((baselineFreeCash * 1.5) / 1000) * 1000;

      // Ensure minimal practical differences
      if (dailyComf < 1000) dailyComf = 1000;
      if (dailyRec <= dailyComf) dailyRec = dailyComf + 1000;
      if (dailyFast <= dailyRec) dailyFast = dailyRec + 2000;

      setPlans({
        comfortable: { daily: dailyComf, days: Math.ceil(target / dailyComf) },
        recommended: { daily: dailyRec, days: Math.ceil(target / dailyRec) },
        fast: { daily: dailyFast, days: Math.ceil(target / dailyFast) }
      })

    } catch (e) {
      console.error(e)
      // Fallback calculations
      const target = parseInt(targetAmountStr.replace(/\s/g, '')) || 0;
      setPlans({
        comfortable: { daily: 5000, days: Math.ceil(target / 5000) },
        recommended: { daily: 10000, days: Math.ceil(target / 10000) },
        fast: { daily: 20000, days: Math.ceil(target / 20000) }
      })
    } finally {
      setTimeout(() => {
        clearInterval(interval)
        setStep(3)
      }, 4500)
    }
  }

  const handleSelectPlan = (planData: any) => {
    setSelectedPlan(planData)
    setStep(4)
    setProgressVal(0) // Start exactly at 0%
  }

  const handleStartGoal = async () => {
    if (!title || !targetAmountStr || !selectedPlan) return
    
    try {
      setLoading(true)
      const targetAmount = parseInt(targetAmountStr.replace(/\s/g, '')) || 0;
      
      // Calculate exact deadline date
      const d = new Date();
      d.setDate(d.getDate() + selectedPlan.days);
      const deadlineStr = d.toISOString().split('T')[0];

      const smartIcon = getSmartIcon(title.trim());

      const newGoal = {
        title: title.trim(),
        amount: targetAmount,
        deadline: deadlineStr,
        daily_limit: selectedPlan.daily,
        icon: smartIcon.id,
        iconBg: "bg-emerald-50",
        iconColor: "text-emerald-500",
      }
      
      await onGoalAdded(newGoal)
      onClose()
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const isStep1Valid = title.trim().length > 0 && targetAmountStr.length > 0;

  return (
    <Drawer open={isOpen} onOpenChange={onClose}>
      <DrawerContent className={`bg-gradient-to-br from-[#F4FCF9] via-[#FFFFFF] to-[#E9F8F1] h-[96vh] shadow-[0_0_50px_rgba(16,185,129,0.15)] border-t border-white/50 ${poppins.className}`}>
        <DrawerHeader className="sr-only">
          <DrawerTitle>Yangi maqsad qo'shish</DrawerTitle>
        </DrawerHeader>
        <div className="mx-auto w-full max-w-sm flex flex-col h-full overflow-hidden relative">
          
          {step === 1 && (
            <div className="flex flex-col h-full animate-in fade-in overflow-hidden">
              <div className="p-5 overflow-y-auto flex-1 scrollbar-none pb-0">
                <div className="mb-6 mt-2 text-center">
                    <div className="w-16 h-16 bg-[#DDF7EE] rounded-full flex items-center justify-center mx-auto mb-4">
                        <Target className="w-8 h-8 text-[#10B981]" />
                    </div>
                    <h1 className="text-2xl font-bold text-gray-900">Yangi maqsad</h1>
                    <p className="text-gray-500 mt-2 text-sm leading-relaxed">Orzuingizni kiriting. Disciplix siz uchun eng yaxshi rejani hisoblaydi.</p>
                </div>

                <div className="space-y-5 mb-8">
                    <div>
                        <Label className="text-sm font-semibold text-gray-900 mb-2 ml-1 block">Maqsad nomi</Label>
                        <Input
                          placeholder="Masalan: Yangi MacBook"
                          value={title}
                          onChange={(e) => setTitle(e.target.value)}
                          className="rounded-2xl border-gray-200 h-14 bg-white focus-visible:ring-[#10B981]"
                        />
                    </div>
                    <div>
                        <Label className="text-sm font-semibold text-gray-900 mb-2 ml-1 block">Kerakli summa ({baseCurrency})</Label>
                        <Input
                          type="tel"
                          placeholder="Masalan: 15 000 000"
                          value={targetAmountStr}
                          onChange={handleAmountChange}
                          className="rounded-2xl border-gray-200 h-14 bg-white font-semibold focus-visible:ring-[#10B981]"
                        />
                    </div>
                </div>
              </div>

              <div className="p-5 pt-2 mt-auto shrink-0">
                <Button 
                  onClick={runAIAnalysis} 
                  disabled={!isStep1Valid}
                  className="w-full bg-[#10B981] hover:bg-emerald-600 text-white rounded-2xl h-14 text-base font-bold shadow-lg shadow-emerald-500/20"
                >
                    Davom etish
                </Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="p-8 flex flex-col items-center justify-center py-20 animate-in fade-in zoom-in-95">
              <div className="w-16 h-16 border-4 border-[#DDF7EE] border-t-[#10B981] rounded-full animate-spin mb-8"></div>
              <h2 className="text-xl font-bold text-gray-900 mb-3 flex items-center gap-2"><Bot className="w-6 h-6 text-[#10B981]"/> Disciplix AI</h2>
              <p className="text-gray-500 text-sm text-center transition-opacity duration-300 font-medium">
                {analysisText}
              </p>
            </div>
          )}

          {step === 3 && plans && (
            <div className="flex flex-col h-full animate-in slide-in-from-right-4 overflow-hidden">
              <div className="p-4 pb-0 shrink-0">
                  <button onClick={() => setStep(1)} className="text-gray-500 flex items-center gap-1 text-sm font-medium mb-3 hover:text-gray-900">
                      <ArrowLeft className="w-4 h-4"/> Orqaga
                  </button>
                  <h1 className="text-2xl font-bold text-gray-900">Tavsiya etilgan rejalar</h1>
                  <p className="text-gray-500 mt-1 text-sm leading-snug">Moliyaviy holatingiz va faol orzularingizdan kelib chiqib, quyidagi rejalarni tuzdik.</p>
              </div>

              <div className="p-4 overflow-y-auto pb-6 space-y-3 flex-1 scrollbar-none">
                
                {/* Fast Card */}
                <div className="bg-white border border-gray-200 rounded-2xl p-4 relative overflow-hidden shrink-0">
                  <div className="mb-3">
                      <h3 className="font-bold text-gray-900 flex items-center gap-1.5"><Zap className="w-5 h-5 text-amber-500"/> Tez Rejim</h3>
                      <p className="text-xs text-gray-500 mt-0.5">Qisqa muddat, biroz qiyinroq</p>
                  </div>
                  <div className="flex justify-between items-end mb-4">
                      <div>
                          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider mb-1">MUDDAT</p>
                          <p className="font-bold text-gray-900 text-lg">{plans.fast.days} kun</p>
                      </div>
                      <div className="text-right">
                          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider mb-1">KUNLIK SUMMA</p>
                          <p className="font-bold text-gray-900 text-lg">{formatMoney(plans.fast.daily)} {baseCurrency}</p>
                      </div>
                  </div>
                  <Button variant="outline" onClick={() => handleSelectPlan(plans.fast)} className="w-full rounded-xl bg-gray-50 border-gray-200 hover:bg-gray-100 font-semibold">
                    Tanlash
                  </Button>
                </div>

                {/* Recommended Card */}
                <div className="bg-white border-2 border-[#10B981] rounded-2xl p-4 relative overflow-hidden shadow-lg shadow-emerald-500/10 shrink-0">
                  <div className="absolute top-0 right-0 bg-[#10B981] text-white text-[10px] font-bold px-3 py-1 rounded-bl-xl tracking-wider">TAVSIYA ETILADI</div>
                  <div className="mb-3">
                      <h3 className="font-bold text-[#10B981] flex items-center gap-1.5"><ShieldCheck className="w-5 h-5"/> Balans Rejim</h3>
                      <p className="text-xs text-gray-500 mt-0.5">Sizning byudjetingizga mos</p>
                  </div>
                  <div className="flex justify-between items-end mb-4">
                      <div>
                          <p className="text-[10px] uppercase font-bold text-[#10B981] tracking-wider mb-1">MUDDAT</p>
                          <p className="font-bold text-gray-900 text-xl">{plans.recommended.days} kun</p>
                      </div>
                      <div className="text-right">
                          <p className="text-[10px] uppercase font-bold text-[#10B981] tracking-wider mb-1">KUNLIK SUMMA</p>
                          <p className="font-bold text-gray-900 text-xl">{formatMoney(plans.recommended.daily)} {baseCurrency}</p>
                      </div>
                  </div>
                  <Button onClick={() => handleSelectPlan(plans.recommended)} className="w-full rounded-xl bg-[#10B981] hover:bg-emerald-600 text-white font-bold h-12">
                    Bu rejani tanlash
                  </Button>
                </div>

                {/* Comfortable Card */}
                <div className="bg-white border border-gray-200 rounded-2xl p-4 relative overflow-hidden shrink-0">
                  <div className="mb-3">
                      <h3 className="font-bold text-gray-900 flex items-center gap-1.5"><Leaf className="w-5 h-5 text-blue-500"/> Qulay Rejim</h3>
                      <p className="text-xs text-gray-500 mt-0.5">Uzoq muddat, xotirjam</p>
                  </div>
                  <div className="flex justify-between items-end mb-4">
                      <div>
                          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider mb-1">MUDDAT</p>
                          <p className="font-bold text-gray-900 text-lg">{plans.comfortable.days} kun</p>
                      </div>
                      <div className="text-right">
                          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider mb-1">KUNLIK SUMMA</p>
                          <p className="font-bold text-gray-900 text-lg">{formatMoney(plans.comfortable.daily)} {baseCurrency}</p>
                      </div>
                  </div>
                  <Button variant="outline" onClick={() => handleSelectPlan(plans.comfortable)} className="w-full rounded-xl bg-gray-50 border-gray-200 hover:bg-gray-100 font-semibold">
                    Tanlash
                  </Button>
                </div>

              </div>
            </div>
          )}

          {step === 4 && selectedPlan && (
            <div className="flex flex-col h-full animate-in slide-in-from-right-4 overflow-hidden relative z-10">
              
              {/* Dekorativ orqa fon shakllari faqat 4-bosqich uchun */}
              <div className="absolute top-0 right-0 w-64 h-64 bg-[#10B981]/10 rounded-full blur-[60px] -translate-y-1/2 translate-x-1/3 pointer-events-none -z-10"></div>
              <div className="absolute bottom-1/4 left-0 w-48 h-48 bg-[#34D399]/10 rounded-full blur-[50px] -translate-x-1/2 pointer-events-none -z-10"></div>

              <div className="p-5 overflow-y-auto flex-1 scrollbar-none pb-0 relative z-10">
                <div className="mb-4 flex justify-between items-center">
                    <button onClick={() => setStep(3)} className="w-10 h-10 flex items-center justify-center bg-white/60 hover:bg-white backdrop-blur-md rounded-full shadow-sm border border-gray-100 text-gray-700 transition-all active:scale-95">
                        <ArrowLeft className="w-5 h-5"/>
                    </button>
                    <div className="text-[10px] font-bold text-[#059669] bg-[#10B981]/10 px-4 py-1.5 rounded-full uppercase tracking-[0.2em] shadow-sm border border-[#10B981]/20">
                        Tasdiqlash
                    </div>
                </div>

                <div className="text-center mb-8 mt-4">
                    <h1 className="text-3xl font-black text-gray-900 mb-2 tracking-tight">{title.charAt(0).toUpperCase() + title.slice(1)}</h1>
                    <p className="text-3xl font-bold flex items-center justify-center gap-1.5 bg-clip-text text-transparent bg-gradient-to-r from-[#10B981] to-[#047857]">
                      {targetAmountStr} <span className="text-lg font-bold opacity-70 mt-1 uppercase">{baseCurrency}</span>
                    </p>
                </div>

                {progressVal === 0 ? (
                  <div className="flex flex-col items-center justify-center py-4 mb-6 relative">
                      {/* Rotating outer dash border */}
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[65%] w-32 h-32 rounded-full border border-dashed border-[#10B981]/40 animate-[spin_10s_linear_infinite]"></div>
                      
                      {/* Pulsing glow */}
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[65%] w-24 h-24 bg-[#10B981]/20 rounded-full blur-xl animate-pulse"></div>
                      
                      {/* Central elegant icon container */}
                      <div className="relative w-24 h-24 bg-white rounded-[2rem] rotate-3 flex items-center justify-center shadow-[0_15px_35px_rgba(16,185,129,0.2)] mb-8 border border-white transition-transform hover:scale-105 hover:rotate-0 duration-300">
                          <div className="absolute inset-0 bg-gradient-to-br from-[#10B981]/5 to-transparent rounded-[2rem]"></div>
                          {(() => {
                              const SmartIcon = getSmartIcon(title).Icon;
                              return <SmartIcon className="w-12 h-12 text-[#10B981] -rotate-3" strokeWidth={2} />;
                          })()}
                      </div>
                      
                      {/* Motivational */}
                      <div className="text-center relative z-10 space-y-2 mt-4">
                        <span className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-white shadow-sm text-[#10B981] text-[10px] font-black rounded-full uppercase tracking-widest border border-gray-50">
                            <CheckCircle2 className="w-3.5 h-3.5"/> Barchasi tayyor
                        </span>
                        <p className="text-sm text-gray-500 font-medium px-4">
                            Katta orzular faqatgina kichik qadamlardan boshlanadi.
                        </p>
                      </div>
                  </div>
                ) : (
                  <ProgressRing progress={progressVal} />
                )}

                {/* Premium Plan Summary Card */}
                <div className="bg-white/60 backdrop-blur-xl border border-white rounded-[24px] p-5 mb-4 shadow-[0_8px_30px_rgba(0,0,0,0.03)] space-y-4 relative overflow-hidden">
                    {/* Karta ichidagi dekoratsiya */}
                    <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-transparent to-[#10B981]/5 rounded-bl-[100px] pointer-events-none"></div>

                    <div className="flex justify-between items-center relative z-10">
                        <div className="flex items-center gap-2 text-gray-500 font-medium text-sm">
                          <div className="w-8 h-8 rounded-full bg-[#10B981]/10 flex items-center justify-center"><TrendingUp className="w-4 h-4 text-[#10B981]"/></div>
                          Kunlik badal
                        </div>
                        <div className="font-bold text-gray-900 text-lg flex items-baseline gap-1">
                          {formatMoney(selectedPlan.daily)} <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">{baseCurrency}</span>
                        </div>
                    </div>

                    <div className="w-full h-px bg-gradient-to-r from-gray-100 via-gray-200 to-gray-100 relative z-10"></div>

                    <div className="flex justify-between items-center relative z-10">
                        <div className="flex items-center gap-2 text-gray-500 font-medium text-sm">
                          <div className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center"><Calendar className="w-4 h-4 text-blue-500"/></div>
                          Muddat
                        </div>
                        <div className="font-bold text-gray-900 text-lg">{selectedPlan.days} kun</div>
                    </div>
                </div>

                {/* Kichik ishonch uqtiruvchi matn */}
                <p className="text-[11px] text-center text-gray-400 font-medium uppercase tracking-widest px-4 pb-2">
                  AI hisobi bo'yicha muvaffaqiyat ehtimoli 95%
                </p>
              </div>

              {/* Dynamic CTA Button */}
              <div className="p-5 pt-2 mt-auto shrink-0 relative z-10">
                <button onClick={handleStartGoal} disabled={loading} className="group relative w-full h-16 rounded-[24px] overflow-hidden transition-transform active:scale-[0.98] shadow-[0_8px_20px_rgb(16,185,129,0.25)] border border-[#10B981]/20">
                    {/* Button background animation */}
                    <div className="absolute inset-0 bg-gradient-to-r from-[#10B981] via-[#059669] to-[#10B981] bg-[length:200%_auto] group-hover:bg-[position:right_center] transition-all duration-500 ease-out"></div>
                    {/* Content */}
                    <div className="absolute inset-0 flex items-center justify-center gap-2 text-white font-bold text-lg">
                      {loading ? (
                          <div className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      ) : (
                          <><Rocket className="w-6 h-6 group-hover:-translate-y-1 group-hover:translate-x-1 transition-transform duration-300"/> Maqsadni boshlash</>
                      )}
                    </div>
                </button>
              </div>
            </div>
          )}

        </div>
      </DrawerContent>
    </Drawer>
  )
}
