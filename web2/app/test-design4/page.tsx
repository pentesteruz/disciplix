"use client"

import { ArrowLeft, Home, Rocket, CheckCircle2, Calendar, TrendingUp } from "lucide-react"
import { Poppins } from "next/font/google"

const poppins = Poppins({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800", "900"] })

export default function TestDesign4Page() {
  const title = "Orzu qilingan Uycha"
  const targetAmountStr = "4 645 654"
  const selectedPlan = { daily: 45000, days: 180 }
  const formatMoney = (amount: number) => amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");

  return (
    <div className={`min-h-screen bg-black/60 flex items-end justify-center sm:items-center ${poppins.className}`}>
      
      {/* Asosiy Karta - Glassmorphism va Mesh Gradient aralashmasi */}
      <div className="bg-gradient-to-br from-[#F4FCF9] via-[#FFFFFF] to-[#E9F8F1] w-full max-w-sm rounded-t-[2.5rem] sm:rounded-[2.5rem] p-6 overflow-hidden flex flex-col relative h-[90vh] sm:h-[85vh] shadow-[0_0_50px_rgba(16,185,129,0.15)] border-t border-white/50">
        
        {/* Dekorativ orqa fon shakllari */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-[#10B981]/10 rounded-full blur-[60px] -translate-y-1/2 translate-x-1/3"></div>
        <div className="absolute bottom-1/4 left-0 w-48 h-48 bg-[#34D399]/10 rounded-full blur-[50px] -translate-x-1/2"></div>

        <div className="overflow-y-auto flex-1 scrollbar-none pb-0 relative z-10">
          
          {/* Top Header */}
          <div className="mb-4 flex justify-between items-center">
              <button className="w-10 h-10 flex items-center justify-center bg-white/60 hover:bg-white backdrop-blur-md rounded-full shadow-sm border border-gray-100 text-gray-700 transition-all active:scale-95">
                  <ArrowLeft className="w-5 h-5"/>
              </button>
              <div className="text-[10px] font-bold text-[#059669] bg-[#10B981]/10 px-4 py-1.5 rounded-full uppercase tracking-[0.2em] shadow-sm border border-[#10B981]/20">
                  Tasdiqlash
              </div>
          </div>

          {/* Title & Amount (Text Gradient) */}
          <div className="text-center mb-8 mt-4">
              <h1 className="text-3xl font-black text-gray-900 mb-2 tracking-tight">{title}</h1>
              <p className="text-3xl font-bold flex items-center justify-center gap-1.5 bg-clip-text text-transparent bg-gradient-to-r from-[#10B981] to-[#047857]">
                {targetAmountStr} <span className="text-lg font-bold opacity-70 mt-1 uppercase">UZS</span>
              </p>
          </div>

          {/* Centerpiece - Premium Rotating Glow */}
          <div className="flex flex-col items-center justify-center py-4 mb-6 relative">
              {/* Rotating outer dash border */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[65%] w-32 h-32 rounded-full border border-dashed border-[#10B981]/40 animate-[spin_10s_linear_infinite]"></div>
              
              {/* Pulsing glow */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[65%] w-24 h-24 bg-[#10B981]/20 rounded-full blur-xl animate-pulse"></div>
              
              {/* Central elegant icon container */}
              <div className="relative w-24 h-24 bg-white rounded-[2rem] rotate-3 flex items-center justify-center shadow-[0_15px_35px_rgba(16,185,129,0.2)] mb-8 border border-white transition-transform hover:scale-105 hover:rotate-0 duration-300">
                  <div className="absolute inset-0 bg-gradient-to-br from-[#10B981]/5 to-transparent rounded-[2rem]"></div>
                  <Home className="w-12 h-12 text-[#10B981] -rotate-3" strokeWidth={2} />
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
                    {formatMoney(selectedPlan.daily)} <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">UZS</span>
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
        <div className="pt-2 mt-auto shrink-0 relative z-10">
          <button className="group relative w-full h-16 rounded-[24px] overflow-hidden transition-transform active:scale-[0.98]">
              {/* Button background animation */}
              <div className="absolute inset-0 bg-gradient-to-r from-[#10B981] via-[#059669] to-[#10B981] bg-[length:200%_auto] group-hover:bg-[position:right_center] transition-all duration-500 ease-out"></div>
              {/* Content */}
              <div className="absolute inset-0 flex items-center justify-center gap-2 text-white font-bold text-lg">
                <Rocket className="w-6 h-6 group-hover:-translate-y-1 group-hover:translate-x-1 transition-transform duration-300"/>
                Maqsadni boshlash
              </div>
          </button>
        </div>
      </div>
    </div>
  )
}
