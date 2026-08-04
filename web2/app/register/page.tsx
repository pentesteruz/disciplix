"use client"

import { useState, useEffect } from "react"
import { Wallet, Zap, BarChart2, Info, ArrowRight, ArrowLeft, CheckCircle2, Circle, TrendingDown, Lightbulb, Trash2, Plus, Loader2 } from "lucide-react"
import Script from "next/script"

export default function RegisterPage() {
  const [step, setStep] = useState(1) // 3 steps: 1=Income, 2=Mode, 3=Details
  const [monthlyIncome, setMonthlyIncome] = useState("")
  const [baseCurrency, setBaseCurrency] = useState("UZS")
  const currencies = ["UZS", "RUB", "USD"]
  const [mode, setMode] = useState<"quick" | "detailed">("quick")
  
  // Step 3 - Quick
  const [fixedExpenses, setFixedExpenses] = useState("")
  const [dailyLimit, setDailyLimit] = useState("")
  
  // Step 3 - Detailed
  const [expenses, setExpenses] = useState([{ id: Date.now(), name: "", amount: "", day: "" }])
  
  const [tg, setTg] = useState<any>(null)
  const [telegramId, setTelegramId] = useState<number | null>(null)
  const [refCode, setRefCode] = useState<string | null>(null)
  const [lang, setLang] = useState("uz")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Derived name/surname from TG context
  const [firstName, setFirstName] = useState("Foydalanuvchi")
  const [lastName, setLastName] = useState("")
  
  useEffect(() => {
    if (typeof window === "undefined") return

    const isTelegram = !!(window as any).Telegram?.WebApp?.initData;
    const isLocalDev = process.env.NODE_ENV === "development";
    if (!isTelegram && !isLocalDev) {
      window.location.href = "https://disciplix.uz";
      return;
    }

    if ((window as any).Telegram?.WebApp) {
      const webApp = (window as any).Telegram.WebApp
      webApp.expand()
      setTg(webApp)
      const tgUser = webApp.initDataUnsafe?.user
      if (tgUser?.id) setTelegramId(tgUser.id)
      if (tgUser?.first_name) setFirstName(tgUser.first_name)
      if (tgUser?.last_name) setLastName(tgUser.last_name)
    }
    
    const urlParams = new URLSearchParams(window.location.search)
    setRefCode(urlParams.get('ref'))
    if (urlParams.get('lang')) setLang(urlParams.get('lang')!)
    const userIdFromUrl = urlParams.get('user_id')
    if (userIdFromUrl && !telegramId) setTelegramId(Number(userIdFromUrl))
  }, [])

  useEffect(() => {
    if (typeof window === "undefined" || telegramId) return
    const urlParams = new URLSearchParams(window.location.search)
    const userIdFromUrl = urlParams.get('user_id')
    if (userIdFromUrl) setTelegramId(Number(userIdFromUrl))
  }, [telegramId])

  const formatNumber = (val: string) => {
    const num = val.replace(/\D/g, "")
    if (!num) return ""
    return num.replace(/\B(?=(\d{3})+(?!\d))/g, " ")
  }

  const parseNumber = (val: string) => {
    return parseFloat(val.replace(/\s/g, "")) || 0
  }

  const addExpenseRow = () => setExpenses([...expenses, { id: Date.now(), name: "", amount: "", day: "" }])
  const removeExpenseRow = (id: number) => { if (expenses.length > 1) setExpenses(expenses.filter(exp => exp.id !== id)) }
  
  const updateExpense = (id: number, field: string, value: string) => { 
    setExpenses(expenses.map(exp => {
      if (exp.id === id) {
        if (field === "amount") {
          return { ...exp, [field]: formatNumber(value) }
        }
        return { ...exp, [field]: value }
      }
      return exp
    })) 
  }

  const nextStep = () => {
    setError(null)
    if (step === 1) {
      if (!monthlyIncome) {
        setError("Iltimos, oylik daromadingizni kiriting.")
        return
      }
      setStep(2)
    } else if (step === 2) {
      setStep(3)
    }
  }

  const prevStep = () => {
    setError(null)
    if (step > 1) setStep(step - 1)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault()
      if (step < 3) {
        nextStep()
      } else {
        handleSubmit()
      }
    }
  }

  const handleSubmit = async () => {
    setError(null)
    
    if (!telegramId) {
      setError("Telegram ID topilmadi. Iltimos botdan qayta oching.")
      return
    }

    let payload: any = {
      telegram_id: telegramId,
      mode: mode,
      name: firstName,
      surname: lastName,
      monthly_income: parseNumber(monthlyIncome),
      ref: refCode,
      lang,
      base_currency: baseCurrency
    }

    if (mode === "quick") {
      if (!fixedExpenses || !dailyLimit) {
        setError("Iltimos, barcha maydonlarni to'ldiring.")
        return
      }
      payload.fixed_expenses_total = parseNumber(fixedExpenses)
      payload.daily_limit = parseNumber(dailyLimit)
    } else {
      let totalFixed = 0
      const processedExpenses: any[] = []
      let valid = true
      expenses.forEach(exp => {
        if (!exp.name || !exp.amount || !exp.day) {
          valid = false
        } else {
          const amt = parseNumber(exp.amount)
          totalFixed += amt
          processedExpenses.push({ name: exp.name, amount: amt, day: exp.day })
        }
      })
      if (!valid) {
        setError("Barcha xarajat maydonlarini to'ldiring.")
        return
      }
      payload.expenses = processedExpenses
      payload.fixed_expenses_total = totalFixed
    }

    setIsLoading(true)
    try {
      const { tgFetch } = await import('@/lib/api')
      await tgFetch('/api/register', {
        method: 'POST',
        body: JSON.stringify(payload)
      })

      if (tg) {
        tg.showAlert("✅ Muvaffaqiyatli ro'yxatdan o'tdingiz! Endi botdan to'liq foydalanishingiz mumkin.", () => {
          tg.close()
        })
      } else {
        window.location.href = '/'
      }
    } catch (err: any) {
      setError(err?.message || "Noma'lum xatolik")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#F8F9FB] flex flex-col max-w-md mx-auto relative font-sans text-gray-800">
      
      {/* HEADER WITH BACK BUTTON */}
      <div className="pt-6 px-6 h-14 flex items-center justify-between">
        {step > 1 ? (
          <button onClick={prevStep} className="p-2 -ml-2 rounded-full hover:bg-gray-100 transition-colors">
            <ArrowLeft className="w-6 h-6 text-gray-600" />
          </button>
        ) : (
          <div className="w-10"></div>
        )}
      </div>

      <div className="flex-1 px-6 flex flex-col">
        
        {/* STEP 1: MONTHLY INCOME */}
        {step === 1 && (
          <div className="flex-1 flex flex-col space-y-6 animate-in slide-in-from-right-4 duration-300">
            <div className="text-center mt-4">
              <div className="w-16 h-16 bg-[#10B981]/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <Wallet className="w-8 h-8 text-[#10B981]" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">Oylik daromadingiz</h1>
              <p className="text-gray-500 text-[15px] max-w-[250px] mx-auto leading-relaxed">
                Rejani aniq tuzishimiz uchun oylik umumiy daromadingizni kiriting.
              </p>
            </div>

            <div className="mt-8">
              <div className="relative">
                <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                  <span className="text-gray-400 font-bold">{baseCurrency}</span>
                </div>
                <input 
                  type="text" 
                  inputMode="numeric"
                  placeholder="Masalan: 5 000 000" 
                  className="w-full pl-16 pr-4 bg-white border-none shadow-[0_2px_12px_rgba(0,0,0,0.04)] rounded-[16px] h-16 text-xl font-bold focus:outline-none focus:ring-1 focus:ring-[#10B981]"
                  value={monthlyIncome} 
                  onChange={e => setMonthlyIncome(formatNumber(e.target.value))} 
                  onKeyDown={handleKeyDown}
                  autoFocus
                />
              </div>
            </div>

            <div className="flex justify-center gap-3">
              {currencies.map(c => (
                <button
                  key={c}
                  onClick={() => setBaseCurrency(c)}
                  className={`px-5 py-2.5 rounded-xl font-bold transition-all ${baseCurrency === c ? 'bg-[#10B981] text-white shadow-md' : 'bg-white text-gray-500 shadow-[0_2px_8px_rgba(0,0,0,0.04)] hover:bg-gray-50'}`}
                >
                  {c}
                </button>
              ))}
            </div>

            <div className="bg-[#F3F4F6] rounded-[16px] p-4 flex gap-3 mt-auto mb-2">
              <Info className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
              <p className="text-[13px] text-gray-600 leading-relaxed">
                Bu ma'lumot qat'iy sir saqlanadi va faqat sizning kunlik limitlaringizni hisoblash uchun ishlatiladi.
              </p>
            </div>
            
            {error && <div className="text-red-500 text-sm font-medium text-center">{error}</div>}
          </div>
        )}

        {/* STEP 2: METHOD SELECTION */}
        {step === 2 && (
          <div className="flex-1 flex flex-col space-y-6 animate-in slide-in-from-right-4 duration-300">
            <div className="text-center mt-4">
              <h1 className="text-2xl font-bold text-gray-900 mb-2">Qaysi usul sizga mos?</h1>
              <p className="text-gray-500 text-[15px] max-w-[250px] mx-auto leading-relaxed">
                O'zingizga qulay bo'lgan usulni tanlang.
              </p>
            </div>

            <div className="mt-8 space-y-4">
              {/* Tezkor Option */}
              <div 
                onClick={() => setMode("quick")}
                className={`relative bg-white rounded-[20px] p-5 cursor-pointer transition-all border-2 ${mode === 'quick' ? 'border-[#10B981] shadow-md' : 'border-transparent shadow-[0_2px_12px_rgba(0,0,0,0.03)]'}`}
              >
                <div className="flex gap-4">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center shrink-0 ${mode === 'quick' ? 'bg-[#10B981] text-white' : 'bg-gray-100 text-gray-500'}`}>
                    <Zap className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900 text-lg mb-1">Tezkor</h3>
                    <p className="text-[13px] text-gray-500 leading-relaxed">Umumiy xarajat va kunlik limitni kiriting. Tez va oson.</p>
                  </div>
                </div>
                {mode === 'quick' ? (
                  <CheckCircle2 className="absolute top-5 right-5 w-6 h-6 text-[#10B981] fill-[#E8F8F3]" />
                ) : (
                  <Circle className="absolute top-5 right-5 w-6 h-6 text-gray-200" />
                )}
              </div>

              {/* Nazorat Option */}
              <div 
                onClick={() => setMode("detailed")}
                className={`relative bg-white rounded-[20px] p-5 cursor-pointer transition-all border-2 ${mode === 'detailed' ? 'border-[#10B981] shadow-md' : 'border-transparent shadow-[0_2px_12px_rgba(0,0,0,0.03)]'}`}
              >
                <div className="flex gap-4">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center shrink-0 ${mode === 'detailed' ? 'bg-[#6366F1] text-white' : 'bg-gray-100 text-gray-500'}`}>
                    <BarChart2 className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900 text-lg mb-1">Nazorat</h3>
                    <p className="text-[13px] text-gray-500 leading-relaxed">Har bir majburiy xarajatni alohida kiriting. Batafsil nazorat.</p>
                  </div>
                </div>
                {mode === 'detailed' ? (
                  <CheckCircle2 className="absolute top-5 right-5 w-6 h-6 text-[#10B981] fill-[#E8F8F3]" />
                ) : (
                  <Circle className="absolute top-5 right-5 w-6 h-6 text-gray-200" />
                )}
              </div>
            </div>

            <div className="bg-[#F3F4F6] rounded-[16px] p-4 flex gap-3 mt-auto mb-2">
              <Info className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
              <p className="text-[13px] text-gray-600 leading-relaxed">
                Keyinroq istalgan vaqtda usulni o'zgartirishingiz mumkin.
              </p>
            </div>
          </div>
        )}

        {/* STEP 3: DETAILS */}
        {step === 3 && (
          <div className="flex-1 flex flex-col space-y-5 animate-in slide-in-from-right-4 duration-300">
            {/* Top Tab indicator */}
            <div className="bg-gray-100 p-1 rounded-[16px] flex mx-auto w-4/5 mb-2">
              <div className={`flex-1 text-center py-2 rounded-[12px] text-sm font-bold transition-all ${mode === 'quick' ? 'bg-white shadow-sm text-[#10B981]' : 'text-gray-500'}`}>
                Tezkor
              </div>
              <div className={`flex-1 text-center py-2 rounded-[12px] text-sm font-bold transition-all ${mode === 'detailed' ? 'bg-white shadow-sm text-[#10B981]' : 'text-gray-500'}`}>
                Nazorat
              </div>
            </div>

            {mode === "quick" ? (
              <>
                <div className="bg-white border border-gray-100 rounded-[16px] p-4 flex gap-3 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                  <Info className="w-5 h-5 text-[#10B981] flex-shrink-0 mt-0.5" />
                  <p className="text-[13px] text-gray-700 leading-relaxed">
                    Tezkor rejim: Umumiy xarajat va kunlik limitni kiriting.
                  </p>
                </div>

                <div className="space-y-2 mt-4">
                  <label className="text-sm font-semibold text-gray-800">Majburiy xarajatlar ({baseCurrency}/oy)</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                      <TrendingDown className="w-5 h-5 text-red-400" />
                    </div>
                    <input 
                      type="text" 
                      inputMode="numeric"
                      placeholder="Masalan: 2 000 000" 
                      className="w-full pl-12 pr-4 bg-white border-none shadow-[0_2px_12px_rgba(0,0,0,0.04)] rounded-[16px] h-14 text-lg font-medium focus:outline-none focus:ring-1 focus:ring-[#10B981]"
                      value={fixedExpenses} 
                      onChange={e => setFixedExpenses(formatNumber(e.target.value))} 
                      onKeyDown={handleKeyDown}
                      autoFocus
                    />
                  </div>
                </div>

                <div className="space-y-2 mt-4">
                  <label className="text-sm font-semibold text-gray-800">Kunlik limit ({baseCurrency})</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                      <Wallet className="w-5 h-5 text-[#10B981]" />
                    </div>
                    <input 
                      type="text" 
                      inputMode="numeric"
                      placeholder="Masalan: 100 000" 
                      className="w-full pl-12 pr-4 bg-white border-none shadow-[0_2px_12px_rgba(0,0,0,0.04)] rounded-[16px] h-14 text-lg font-medium focus:outline-none focus:ring-1 focus:ring-[#10B981]"
                      value={dailyLimit} 
                      onChange={e => setDailyLimit(formatNumber(e.target.value))} 
                      onKeyDown={handleKeyDown}
                    />
                  </div>
                </div>

                <div className="bg-[#E8F8F3] border border-[#D1F1E7] rounded-[16px] p-4 flex gap-3 mt-auto mb-2">
                  <Lightbulb className="w-5 h-5 text-[#10B981] flex-shrink-0 mt-0.5" />
                  <p className="text-[13px] text-gray-700 leading-relaxed">
                    Siz kiritgan kunlik limit botdagi balansingizga avtomatik o'rnatiladi.
                  </p>
                </div>
              </>
            ) : (
              <>
                <div className="bg-white border border-gray-100 rounded-[16px] p-4 flex gap-3 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                  <Info className="w-5 h-5 text-[#6366F1] flex-shrink-0 mt-0.5" />
                  <p className="text-[13px] text-gray-700 leading-relaxed">
                    Nazorat rejimi: Har bir majburiy xarajatni aniq sanasi bilan kiriting. Limit avtomat hisoblanadi.
                  </p>
                </div>

                <div className="space-y-3 mt-4 max-h-[40vh] overflow-y-auto scrollbar-none pb-2">
                  {expenses.map((expense) => (
                    <div key={expense.id} className="flex gap-2 items-center bg-white p-2 rounded-[16px] shadow-[0_2px_8px_rgba(0,0,0,0.03)] border border-transparent">
                      <div className="grid grid-cols-[2fr_2fr_1fr] gap-2 flex-1">
                        <input 
                          type="text"
                          placeholder="Nomi (Ijara)" 
                          className="w-full px-3 bg-gray-50 border-none shadow-none rounded-[12px] h-12 text-sm focus:outline-none focus:ring-1 focus:ring-[#6366F1]"
                          value={expense.name} 
                          onChange={e => updateExpense(expense.id, 'name', e.target.value)} 
                          onKeyDown={handleKeyDown}
                          autoFocus={expenses.length === 1}
                        />
                        <input 
                          type="text" 
                          inputMode="numeric"
                          placeholder="Summa" 
                          className="w-full px-3 bg-gray-50 border-none shadow-none rounded-[12px] h-12 text-sm text-red-500 font-medium focus:outline-none focus:ring-1 focus:ring-[#6366F1]"
                          value={expense.amount} 
                          onChange={e => updateExpense(expense.id, 'amount', e.target.value)} 
                          onKeyDown={handleKeyDown}
                        />
                        <input 
                          type="number" 
                          placeholder="Kun" 
                          min="1" max="31"
                          className="w-full px-3 bg-gray-50 border-none shadow-none rounded-[12px] h-12 text-sm font-medium text-center focus:outline-none focus:ring-1 focus:ring-[#6366F1]"
                          value={expense.day} 
                          onChange={e => updateExpense(expense.id, 'day', e.target.value)} 
                          onKeyDown={handleKeyDown}
                        />
                      </div>
                      <button 
                        type="button" 
                        className="h-12 w-12 flex items-center justify-center rounded-[12px] text-gray-400 hover:text-red-500 hover:bg-red-50 shrink-0 p-0 transition-colors"
                        onClick={() => removeExpenseRow(expense.id)}
                        disabled={expenses.length === 1}
                      >
                        <Trash2 className="h-5 w-5" />
                      </button>
                    </div>
                  ))}
                </div>
                <button 
                  type="button" 
                  className="w-full mt-2 h-14 flex items-center justify-center rounded-[16px] border-dashed border-2 hover:bg-gray-50 text-gray-500 hover:text-gray-900 transition-all font-semibold" 
                  onClick={addExpenseRow}
                >
                  <Plus className="h-5 w-5 mr-2" /> Yangi xarajat qo'shish
                </button>
              </>
            )}

            {error && <div className="text-red-500 text-sm font-medium text-center">{error}</div>}
          </div>
        )}
      </div>

      {/* FIXED FOOTER WITH BUTTON AND PROGRESS */}
      <div className="px-6 pb-8 pt-4">
        {step < 3 ? (
          <button 
            onClick={nextStep}
            className="w-full h-14 rounded-[16px] text-[16px] font-bold bg-[#10B981] hover:bg-[#0EA5E9] text-white shadow-lg shadow-[#10B981]/25 transition-all active:scale-[0.98] flex items-center justify-between px-6"
          >
            <span>Keyingi qadam</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        ) : (
          <button 
            onClick={handleSubmit}
            disabled={isLoading}
            className="w-full h-14 rounded-[16px] text-[16px] font-bold bg-[#10B981] hover:bg-[#0EA5E9] text-white shadow-lg shadow-[#10B981]/25 transition-all active:scale-[0.98] flex items-center justify-between px-6 disabled:opacity-70 disabled:cursor-not-allowed"
          >
            <span>{isLoading ? "Saqlanmoqda..." : "Boshlash"}</span>
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ArrowRight className="w-5 h-5" />}
          </button>
        )}

        {/* Progress dots */}
        <div className="flex justify-center gap-2 mt-6">
          <div className={`w-2 h-2 rounded-full transition-all duration-300 ${step === 1 ? 'bg-[#10B981] w-4' : 'bg-gray-300'}`}></div>
          <div className={`w-2 h-2 rounded-full transition-all duration-300 ${step === 2 ? 'bg-[#10B981] w-4' : 'bg-gray-300'}`}></div>
          <div className={`w-2 h-2 rounded-full transition-all duration-300 ${step === 3 ? 'bg-[#10B981] w-4' : 'bg-gray-300'}`}></div>
        </div>
      </div>

      <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
    </div>
  )
}
