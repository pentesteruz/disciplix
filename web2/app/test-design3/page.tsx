"use client"

import { ArrowLeft, Home, Rocket } from "lucide-react"
import { Poppins } from "next/font/google"

const poppins = Poppins({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800", "900"] })

export default function TestDesign3Page() {
  const title = "uycha"
  const formattedTitle = title.charAt(0).toUpperCase() + title.slice(1)
  const targetAmountStr = "4 645 654"

  const selectedPlan = { daily: 45000, days: 180 }
  const formatMoney = (amount: number) => amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");

  return (
    <div className={`min-h-screen bg-black/50 flex items-end justify-center sm:items-center ${poppins.className}`}>
      <div className="bg-[#F6FAF8] w-full max-w-sm rounded-t-[2rem] sm:rounded-2xl p-5 overflow-hidden flex flex-col relative h-[90vh] sm:h-auto shadow-2xl">
        <div className="overflow-y-auto flex-1 scrollbar-none pb-0">
          
          {/* Top Header */}
          <div className="mb-2 flex justify-between items-center">
              <button className="text-gray-700 flex items-center gap-1 text-sm font-semibold hover:text-gray-900 transition-colors">
                  <ArrowLeft className="w-4 h-4"/> Orqaga
              </button>
              <div className="text-[10px] font-bold text-[#10B981] bg-[#DDF7EE] px-3 py-1 rounded-full uppercase tracking-widest shadow-sm">
                  Tasdiqlash
              </div>
          </div>

          {/* Below Header */}
          <div className="text-center mb-6 mt-5">
              <h1 className="text-3xl font-extrabold text-gray-900 mb-2">{formattedTitle}</h1>
              <p className="text-2xl font-bold text-[#10B981] flex items-center justify-center gap-1.5">
                {targetAmountStr} <span className="text-base font-bold opacity-80 mt-1">UZS</span>
              </p>
          </div>

          {/* Centerpiece: No progress rings! */}
          <div className="flex flex-col items-center justify-center py-6 mb-4 relative">
              {/* Animated background glow (Soya) */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 bg-[#10B981]/25 rounded-full blur-2xl"></div>
              
              {/* Outer Mint Circle (Thinner) */}
              <div className="relative w-24 h-24 bg-gradient-to-tr from-[#DDF7EE] to-[#ecfbf5] rounded-full flex items-center justify-center shadow-[0_10px_30px_rgb(16,185,129,0.25)] mb-6">
                <div className="w-20 h-20 bg-white rounded-full flex items-center justify-center shadow-md">
                    <Home className="w-10 h-10 text-[#10B981]" strokeWidth={2.5} />
                </div>
              </div>
              
              {/* Below Centerpiece */}
              <div className="text-center relative z-10 space-y-3">
                <span className="inline-block px-4 py-1.5 bg-[#10B981]/10 text-[#10B981] text-xs font-black rounded-full uppercase tracking-widest">
                    🚀 TAYYOR
                </span>
                <p className="text-[13px] text-gray-500 font-medium italic mt-2">
                    "Katta orzular kichik qadamlardan boshlanadi."
                </p>
              </div>
          </div>

          {/* Plan Summary Card */}
          <div className="bg-white border border-gray-100 rounded-[20px] p-5 mb-6 shadow-sm">
              <div className="flex justify-between items-center border-b border-gray-50 pb-3 mb-3">
                  <div className="text-gray-500 text-sm font-medium">Kunlik badal</div>
                  <div className="font-bold text-gray-900 text-lg flex items-center gap-1">
                    {formatMoney(selectedPlan.daily)} <span className="text-[11px] text-gray-400 font-bold uppercase tracking-wider">UZS</span>
                  </div>
              </div>
              <div className="flex justify-between items-center border-b border-gray-50 pb-3 mb-3">
                  <div className="text-gray-500 text-sm font-medium">Muddat</div>
                  <div className="font-bold text-gray-900 text-lg">{selectedPlan.days} kun</div>
              </div>
              <div className="flex justify-between items-center">
                  <div className="text-gray-500 text-sm font-medium">Muvaffaqiyat ehtimoli</div>
                  <div className="font-bold text-[#10B981] text-lg">95%</div>
              </div>
          </div>
        </div>

        {/* Bottom */}
        <div className="pt-2 mt-auto shrink-0 pb-2">
          <button 
            className="w-full bg-[#10B981] hover:bg-emerald-600 text-white rounded-[20px] h-16 text-lg font-bold shadow-[0_8px_20px_rgb(16,185,129,0.25)] flex flex-row items-center justify-center gap-2 transition-transform active:scale-[0.98]"
          >
              <Rocket className="w-6 h-6"/>
              <span>Maqsadni boshlash</span>
          </button>
        </div>
      </div>
    </div>
  )
}
