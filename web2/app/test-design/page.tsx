"use client"

import { ArrowLeft, Target, Rocket } from "lucide-react"
import { Poppins } from "next/font/google"

const poppins = Poppins({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800", "900"] })

export default function TestDesignPage() {
  const title = "uycha"
  const formattedTitle = title.charAt(0).toUpperCase() + title.slice(1)
  const targetAmountStr = "4 645 654"

  const selectedPlan = { daily: 45000, days: 180 }
  const formatMoney = (amount: number) => amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");

  return (
    <div className={`min-h-screen bg-black/50 flex items-end justify-center sm:items-center ${poppins.className}`}>
      <div className="bg-[#F6FAF8] w-full max-w-sm rounded-t-[2rem] sm:rounded-2xl p-5 overflow-hidden flex flex-col relative h-[90vh] sm:h-auto">
        <div className="overflow-y-auto flex-1 scrollbar-none pb-0">
          
          <div className="mb-2 flex justify-between items-center">
              {/* Orqaga tugmasi to'qroq kulrang */}
              <button className="text-gray-700 flex items-center gap-1 text-sm font-semibold hover:text-gray-900 transition-colors">
                  <ArrowLeft className="w-4 h-4"/> Orqaga
              </button>
              <div className="text-[10px] font-bold text-[#10B981] bg-[#DDF7EE] px-3 py-1 rounded-full uppercase tracking-wide">
                  Tasdiqlash
              </div>
          </div>

          <div className="text-center mb-6 mt-4">
              {/* Bosh harf bilan */}
              <h1 className="text-2xl font-bold text-gray-900 mb-2">{formattedTitle}</h1>
              {/* UZS sal kichikroq va uzoqroq */}
              <p className="text-xl font-semibold text-[#10B981] flex items-center justify-center gap-1.5">
                {targetAmountStr} <span className="text-sm font-bold opacity-80 mt-0.5">UZS</span>
              </p>
          </div>

          <div className="flex flex-col items-center justify-center py-4 mb-6 relative">
              {/* Progress bar o'rniga vizual progress (to'lib boruvchi chiziq) */}
              <div className="relative w-28 h-28 flex items-center justify-center mb-4">
                <svg className="absolute inset-0 w-full h-full transform -rotate-90">
                  <circle cx="56" cy="56" r="52" fill="none" stroke="#E5E7EB" strokeWidth="6" />
                  <circle cx="56" cy="56" r="52" fill="none" stroke="#10B981" strokeWidth="6" strokeDasharray="326" strokeDashoffset="326" className="transition-all duration-1000 ease-out" />
                </svg>
                <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-sm relative z-10">
                  <Target className="w-8 h-8 text-[#10B981]" />
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
                  <div className="font-bold text-gray-900 text-lg flex items-center gap-1">
                    {formatMoney(selectedPlan.daily)} <span className="text-xs text-gray-400">UZS</span>
                  </div>
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
            className="w-full bg-[#10B981] hover:bg-emerald-600 text-white rounded-2xl h-14 text-lg font-bold shadow-lg shadow-emerald-500/20 flex flex-row items-center justify-center gap-2 transition-transform active:scale-[0.98]"
          >
              <Rocket className="w-5 h-5"/>
              <span>Maqsadni boshlash</span>
          </button>
        </div>
      </div>
    </div>
  )
}
