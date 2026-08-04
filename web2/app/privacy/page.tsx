import React from "react"

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F8F9FB] via-[#F8F9FB] to-[#E8F8F3] text-gray-800 p-4 md:p-8 font-sans selection:bg-[#10B981]/30 flex items-center justify-center">
      <div className="max-w-3xl w-full mx-auto bg-white rounded-[24px] p-6 md:p-10 border-2 border-[#10B981]/20 shadow-[0_12px_40px_rgba(16,185,129,0.08)] relative overflow-hidden">
        
        {/* Decorative background element */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 rounded-full bg-gradient-to-br from-[#10B981]/10 to-transparent blur-3xl pointer-events-none"></div>
        
        <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 mb-6 border-b border-gray-100 pb-4">
          🔒 Maxfiylik Siyosati va Foydalanish Qoidalari
        </h1>
        
        <p className="text-gray-600 text-lg mb-8 leading-relaxed">
          Disciplix xizmatidan foydalanishni davom ettirish orqali siz quyidagi shartlarga rozilik bildirasiz.
        </p>

        {/* MAXFIYLIK SIYOSATI */}
        <div className="space-y-6 mb-12">
          <h2 className="text-xl md:text-2xl font-bold text-gray-900 mb-4 flex items-center">
            <span className="text-[#10B981] mr-2">🔒</span> Maxfiylik Siyosati
          </h2>
          
          <div className="space-y-6">
            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">1. Ma'lumotlarni saqlash</h3>
              <p className="text-gray-600 leading-relaxed">Disciplix siz tomonidan kiritilgan moliyaviy ma'lumotlar, maqsadlar, vazifalar va ilova faoliyati bilan bog'liq ma'lumotlarni xizmatning ishlashi uchun saqlashi mumkin.</p>
            </section>

            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">2. Ma'lumotlardan foydalanish</h3>
              <p className="text-gray-600 leading-relaxed mb-3">Yig'ilgan ma'lumotlar quyidagi maqsadlarda ishlatiladi:</p>
              <ul className="list-disc list-inside space-y-1 text-gray-600 ml-2">
                <li>Moliyaviy statistika va hisobotlarni shakllantirish;</li>
                <li>Kunlik limit va tavsiyalarni hisoblash;</li>
                <li>Maqsadlar va vazifalarni boshqarish;</li>
                <li>Xizmat sifatini yaxshilash.</li>
              </ul>
            </section>

            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">3. Ma'lumotlarni himoya qilish</h3>
              <p className="text-gray-600 leading-relaxed">Disciplix foydalanuvchi ma'lumotlarini himoya qilish uchun zarur texnik va tashkiliy choralarni ko'radi.</p>
            </section>

            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">4. Uchinchi shaxslar</h3>
              <p className="text-gray-600 leading-relaxed">Foydalanuvchi ma'lumotlari uchinchi shaxslarga sotilmaydi va ularga berilmaydi, qonunchilik talab qilgan holatlar bundan mustasno.</p>
            </section>

            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">5. Ma'lumotlarni o'chirish</h3>
              <p className="text-gray-600 leading-relaxed">Foydalanuvchi istalgan vaqtda ma'lumotlarini o'chirishni so'rashi mumkin. Buning uchun administrator bilan bog'lanish yoki ilovadagi tegishli funksiyadan foydalanish mumkin.</p>
            </section>
          </div>
        </div>

        <hr className="border-gray-100 my-10" />

        {/* FOYDALANISH QOIDALARI */}
        <div className="space-y-6 mb-12">
          <h2 className="text-xl md:text-2xl font-bold text-gray-900 mb-4 flex items-center">
            <span className="text-[#10B981] mr-2">📜</span> Foydalanish Qoidalari
          </h2>

          <div className="space-y-6">
            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">1. Halol foydalanish</h3>
              <p className="text-gray-600 leading-relaxed">Foydalanuvchi Disciplix xizmatidan faqat qonuniy va halol maqsadlarda foydalanishi kerak.</p>
            </section>

            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">2. Referal tizimi</h3>
              <p className="text-gray-600 leading-relaxed">Soxta akkauntlar yaratish, referal tizimini suiiste'mol qilish yoki mukofotlarni noqonuniy olishga urinish taqiqlanadi.</p>
            </section>

            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">3. Premium xizmatlar</h3>
              <p className="text-gray-600 leading-relaxed">Soxta Premium so'rovlari yuborish, to'lov tizimini aldash yoki avtomatlashtirilgan firibgarlik harakatlari taqiqlanadi.</p>
            </section>

            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">4. Cheklovlar</h3>
              <p className="text-gray-600 leading-relaxed mb-3">Qoidabuzarlik aniqlangan taqdirda Disciplix quyidagi choralarni qo'llash huquqiga ega:</p>
              <ul className="list-disc list-inside space-y-1 text-gray-600 ml-2">
                <li>Ogohlantirish;</li>
                <li>Hisobni vaqtinchalik cheklash;</li>
                <li>Premium imkoniyatlarni bekor qilish;</li>
                <li>Hisobni doimiy bloklash.</li>
              </ul>
            </section>

            <section className="bg-gray-50/50 p-5 rounded-[16px] border border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 mb-2">5. Xizmatdagi o'zgarishlar</h3>
              <p className="text-gray-600 leading-relaxed">Disciplix istalgan vaqtda xizmat funksiyalari, qoidalari yoki tariflariga o'zgartirish kiritish huquqini saqlab qoladi.</p>
            </section>
          </div>
        </div>

        <hr className="border-gray-100 my-10" />

        {/* MUHIM ESLATMA */}
        <div className="bg-rose-50 border border-rose-100 rounded-[16px] p-6 mb-8 text-center md:text-left">
          <h2 className="text-xl font-bold text-rose-500 mb-4 flex items-center justify-center md:justify-start">
            <span className="mr-2">⚠️</span> Muhim Eslatma
          </h2>
          <p className="text-rose-700 leading-relaxed mb-4">
            Disciplix moliyaviy rejalashtirish va intizomni rivojlantirish uchun mo'ljallangan xizmat hisoblanadi.
          </p>
          <p className="text-rose-700 leading-relaxed">
            Ilova tomonidan taqdim etilgan tavsiyalar faqat axborot va rejalashtirish maqsadida beriladi hamda professional moliyaviy maslahat o'rnini bosmaydi.
          </p>
        </div>

        {/* ROZILIK */}
        <div className="bg-[#E8F8F3] border border-[#D1F1E7] rounded-[16px] p-6 text-center">
          <p className="text-[#059669] font-bold text-lg leading-relaxed">
            ✅ "Roziman" tugmasini bosish orqali siz Maxfiylik Siyosati va Foydalanish Qoidalarini qabul qilganingizni tasdiqlaysiz.
          </p>
        </div>

      </div>
    </div>
  )
}
