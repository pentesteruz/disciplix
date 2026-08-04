"use client"

import { ArrowLeft, Target, Rocket } from "lucide-react"

export default function TestDesignOldPage() {
  const title = "uycha" // Eskisi kabi kichik harfda
  const targetAmountStr = "4 645 654"

  const selectedPlan = { daily: 45000, days: 180 }
  const formatMoney = (amount: number) => amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");

  return (
    <div className="min-h-screen bg-black/50 flex items-end justify-center sm:items-center">
      <div className="bg-[#F6FAF8] w-full max-w-sm rounded-t-[2rem] sm:rounded-2xl p-5 overflow-hidden flex flex-col relative h-[90vh] sm:h-auto">
        <div className="overflow-y-auto flex-1 scrollbar-none pb-0">
          
          <div className="mb-2 flex justify-between items-center">
              <button className="text-gray-500 flex items-center gap-1 text-sm font-medium hover:text-gray-900">
                  <ArrowLeft className="w-4 h-4"/> Orqaga
              </button>
              <div className="text-[10px] font-bold text-[#10B981] bg-[#DDF7EE] px-3 py-1 rounded-full uppercase tracking-wide">
                  Tasdiqlash
              </div>
          </div>

          <div className="text-center mb-4 mt-2">
              <h1 className="text-2xl font-bold text-gray-900 mb-1">{title}</h1>
              <p className="text-lg font-semibold text-[#10B981]">{targetAmountStr} UZS</p>
          </div>

          <div className="flex flex-col items-center justify-center py-6 mb-4 relative">
              {/* Animated background glow */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-28 h-28 bg-[#10B981]/20 rounded-full blur-2xl animate-pulse"></div>
              
              <div className="relative w-24 h-24 bg-gradient-to-tr from-[#DDF7EE] to-white rounded-full flex items-center justify-center shadow-inner border border-[#10B981]/10 mb-5">
                <div className="w-14 h-14 bg-white rounded-full flex items-center justify-center shadow-sm">
                    <Target className="w-7 h-7 text-[#10B981]" />
                </div>
              </div>
              <div className="text-center relative z-10 space-y-3">
                <span className="inline-block px-3 py-1 bg-[#10B981]/10 text-[#10B981] text-[11px] font-bold rounded-full uppercase tracking-widest">
                    🚀 TAYYOR
                </span>
                <p className="text-[13px] text-gray-500 font-medium italic">
                    "Katta orzular kichik qadamlardan boshlanadi."
                </p>
              </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-2xl p-4 mb-6 shadow-sm">
              <div className="flex justify-between items-center border-b border-gray-100 pb-3 mb-3">
                  <div className="text-gray-500 text-sm font-medium">Kunlik badal</div>
                  <div className="font-bold text-gray-900 text-lg">{formatMoney(selectedPlan.daily)} UZS</div>
              </div>
              <div className="flex justify-between items-center border-b border-gray-100 pb-3 mb-3">
                  <div className="text-gray-500 text-sm font-medium">Muddat</div>
                  <div className="font-bold text-gray-900 text-lg">{selectedPlan.days} kun</div>
              </div>
              <div className="flex justify-between items-center">
                  <div className="text-gray-500 text-sm font-medium">Muvaffaqiyat ehtimoli</div>
                  <div className="font-bold text-[#10B981] text-lg">95%</div>
              </div>
          </div>

          <div className="bg-[#DDF7EE] rounded-xl p-4 mb-2 text-center">
              <p className="text-sm text-[#10B981] font-medium leading-relaxed">
                  "Disciplix hisobiga ko'ra siz ushbu maqsadga xotirjam erisha olasiz. Boshlaymizmi?"
              </p>
          </div>
        </div>

        <div className="pt-4 mt-auto shrink-0">
          <button 
            className="w-full bg-[#10B981] hover:bg-emerald-600 text-white rounded-2xl h-14 text-lg font-bold shadow-lg shadow-emerald-500/20 inline-flex items-center justify-center"
          >
              <Rocket className="w-5 h-5 mr-2"/> Maqsadni boshlash
          </button>
        </div>
      </div>
    </div>
  )
}
