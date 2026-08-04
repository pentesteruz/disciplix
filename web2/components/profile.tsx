"use client"

import { useState, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { useTelegram } from "@/lib/telegram-provider"
import { getProfileStats, updateLanguage, updateBaseCurrency, requestHelp } from "@/lib/api"
import { 
  User, 
  Users, 
  Wallet, 
  CheckCircle, 
  Copy, 
  Settings,
  Bell,
  Globe,
  HelpCircle,
  ChevronRight,
  Flame,
  Crown
} from "lucide-react"
import { useTranslation } from "@/lib/i18n"

// Consistent number formatting
function formatNumber(num: number): string {
  if (!num) return "0"
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

export function Profile() {
  const { user } = useTelegram()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)
  
  const t = useTranslation(data?.user_language || user?.language_code)

  useEffect(() => {
    if (user?.id) {
      getProfileStats(user.id)
        .then(setData)
        .catch(console.error)
        .finally(() => setLoading(false))
    }
  }, [user])

  const handleCopy = async () => {
    if (!data?.referral?.code) return;
    const botUsername = "DisciplixAppBot" // Fallback, could be dynamic
    await navigator.clipboard.writeText(`https://t.me/${botUsername}?start=${data.referral.code}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleNotificationsClick = () => {
    if (typeof window !== "undefined" && (window as any).Telegram?.WebApp) {
      const tg = (window as any).Telegram.WebApp;
      tg.showAlert("Agar siz bildirishnoma yoqmoqchi bo'lsangiz botning xabarnomasini (ovozini/notifikatsiyasini) Telegram sozlamalaridan yoqib qo'ying.");
    } else {
      alert("Agar siz bildirishnoma yoqmoqchi bo'lsangiz botning xabarnomasini (ovozini/notifikatsiyasini) Telegram sozlamalaridan yoqib qo'ying.");
    }
  }

  const handleLanguageClick = () => {
    if (typeof window !== "undefined" && (window as any).Telegram?.WebApp?.showPopup) {
      const tg = (window as any).Telegram.WebApp;
      tg.showPopup({
        title: "Tilni tanlang (Choose language)",
        message: "Iltimos, kerakli tilni tanlang:\nПожалуйста, выберите язык:",
        buttons: [
          { id: "uz", type: "default", text: "O'zbekcha 🇺🇿" },
          { id: "ru", type: "default", text: "Русский 🇷🇺" },
          { id: "en", type: "default", text: "English 🇬🇧" }
        ]
      }, async (buttonId: string) => {
        if (buttonId && user?.id) {
          try {
            await updateLanguage(user.id, buttonId);
            tg.showAlert("✅ Til o'zgartirildi! / Язык изменен!", () => {
              window.location.reload();
            });
          } catch (e) {
            tg.showAlert("Xatolik yuz berdi.");
          }
        }
      });
    }
  }

  const handleCurrencyClick = () => {
    if (typeof window !== "undefined" && (window as any).Telegram?.WebApp?.showPopup) {
      const tg = (window as any).Telegram.WebApp;
      tg.showPopup({
        title: "Asosiy valyutani tanlang",
        message: "Platforma qaysi valyutada hisoblanishini xohlaysiz?",
        buttons: [
          { id: "UZS", type: "default", text: "UZS (So'm)" },
          { id: "USD", type: "default", text: "USD ($)" },
          { id: "RUB", type: "default", text: "RUB (₽)" }
        ]
      }, async (buttonId: string) => {
        if (buttonId && user?.id) {
          try {
            await updateBaseCurrency(user.id, buttonId);
            tg.showAlert(`✅ Asosiy valyuta o'zgartirildi: ${buttonId}`, () => {
              window.location.reload();
            });
          } catch (e) {
            tg.showAlert("Xatolik yuz berdi.");
          }
        }
      });
    }
  }

  const handleHelpClick = async () => {
    if (user?.id) {
       try {
         await requestHelp(user.id);
         if (typeof window !== "undefined" && (window as any).Telegram?.WebApp) {
           (window as any).Telegram.WebApp.close();
         }
       } catch (e) {
         console.error("Help error:", e);
       }
    }
  }

  if (loading || !data) {
    return <div className="p-5 flex justify-center items-center h-screen text-muted-foreground animate-pulse">{t("Loading...")}</div>
  }

  const profileDetails = {
    name: data.name,
    avatar: user?.photo_url || "/placeholder-user.jpg",
    isPro: data.proStatus === "Pro",
    disciplineLevel: data.disciplineLevel,
    disciplineScore: data.tasksCompleted > 0 ? data.tasksCompleted : 50 // Baseline
  }
  
  const stats = {
    totalSaved: data.totalSaved || 0,
    tasksCompleted: data.tasksCompleted || 0,
    spendingStatus: data.spendingStatus || "Yaxshi"
  }
  
  const referral = data.referral || { earnings: 0, invitedCount: 0, recentInvites: [], code: user?.id }

  return (
    <div className="p-5 space-y-6 pb-24">
      {/* Profile Header */}
      <div className="flex items-center gap-4">
        <Avatar className="h-20 w-20 border-4 border-primary/20">
          <AvatarImage src={profileDetails.avatar} alt={profileDetails.name} />
          <AvatarFallback className="bg-primary/10 text-primary text-xl font-semibold">
            {profileDetails.name.split(' ').map((n: string) => n[0]).join('').substring(0, 2) || "U"}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-foreground">{profileDetails.name}</h1>
            {profileDetails.isPro ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-semibold">
                <Crown className="h-3 w-3" />
                {t("Pro")}
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded-full bg-muted text-muted-foreground text-xs font-medium">
                {t("Basic")}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <Flame className="h-4 w-4 text-orange-500" />
            <span className="text-sm text-muted-foreground">
              {t("Discipline Level")}: <span className="font-semibold text-foreground">{profileDetails.disciplineLevel}</span>
            </span>
          </div>
        </div>
      </div>
      
      {/* AI Discipline Summary */}
      <Card className="p-4 bg-gradient-to-r from-primary/10 to-accent/10 border-primary/20 rounded-2xl">
        <p className="text-sm text-foreground">
          <span className="font-semibold">{t("AI Analysis")}</span> {data.aiAnalysis} {t("Overall Discipline")}: {profileDetails.disciplineScore}%.
        </p>
      </Card>
      
      {/* Performance Stats */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-3">{t("General Stats")}</h2>
        <div className="grid grid-cols-3 gap-3">
          <Card className="p-4 text-center bg-card rounded-2xl flex flex-col justify-center items-center">
            <Wallet className="h-6 w-6 text-primary mb-2" />
            <p className="text-[10px] text-muted-foreground mb-1 whitespace-nowrap">{t("Gathering")}</p>
            <p className="text-sm font-bold text-foreground truncate w-full" title={formatNumber(stats.totalSaved)}>{formatNumber(stats.totalSaved)}</p>
          </Card>
          <Card className="p-4 text-center bg-card rounded-2xl flex flex-col justify-center items-center">
            <CheckCircle className="h-6 w-6 text-primary mb-2" />
            <p className="text-[10px] text-muted-foreground mb-1 whitespace-nowrap">{t("Plans")}</p>
            <p className="text-2xl font-bold text-foreground">{stats.tasksCompleted}%</p>
          </Card>
          <Card className="p-4 text-center bg-card rounded-2xl flex flex-col justify-center items-center">
            <Settings className="h-6 w-6 text-primary mb-2" />
            <p className="text-[10px] text-muted-foreground mb-1 whitespace-nowrap">{t("Expenses")}</p>
            <p className="text-sm font-bold text-primary truncate w-full">{stats.spendingStatus}</p>
          </Card>
        </div>
      </div>
      
      {/* Referral Program Section */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-3">{t("Referral Program")}</h2>
        
        {/* Earnings Card */}
        <Card className="p-5 bg-gradient-to-br from-primary to-primary/80 text-primary-foreground mb-4 rounded-3xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm opacity-90">{t("Referral Income")}</p>
              <p className="text-3xl font-bold">{formatNumber(referral.earnings)}</p>
            </div>
            <div className="text-right">
              <div className="w-14 h-14 rounded-full bg-white/20 flex items-center justify-center mb-1 mx-auto">
                <Users className="h-7 w-7" />
              </div>
              <p className="text-sm opacity-90">{referral.invitedCount} {t("friends")}</p>
            </div>
          </div>
        </Card>
        
        {/* Recent Invites List */}
        <Card className="p-4 bg-card mb-4 rounded-2xl">
          <h3 className="text-sm font-semibold text-foreground mb-3">{t("Recent Invites")}</h3>
          <div className="space-y-3">
            {referral.recentInvites.length === 0 ? (
                <div className="text-center text-sm text-muted-foreground">{t("No invites yet")}</div>
            ) : referral.recentInvites.map((invite: any, index: number) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                    <User className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{invite.name}</p>
                    <p className="text-xs text-muted-foreground">{invite.date}</p>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                  {t("Active")}
                </span>
              </div>
            ))}
          </div>
        </Card>
        
        {/* Referral Link Box */}
        <Card className="p-4 bg-card rounded-2xl">
          <p className="text-sm font-medium text-foreground mb-2">{t("Your Referral Link")}</p>
          <div className="flex gap-2">
            <div className="flex-1 px-3 py-2.5 bg-muted rounded-xl text-sm text-muted-foreground truncate flex items-center">
              https://t.me/DisciplixAppBot?start={referral.code}
            </div>
            <Button 
              onClick={handleCopy}
              className="px-4 rounded-xl bg-primary hover:bg-primary/90"
            >
              {copied ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-3 text-center">
            {t("For every")} {referral.bonusReq || 4} {t("friends you get")} <span className="font-semibold text-primary">{referral.bonusDays || 10} {t("days Premium")}</span> {t("bonus")}
          </p>
        </Card>
      </div>
      
      {/* Settings & Navigation */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-3">{t("Settings")}</h2>
        <Card className="bg-card divide-y divide-border rounded-2xl overflow-hidden">
          <button onClick={handleNotificationsClick} className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Bell className="h-5 w-5 text-primary" />
              </div>
              <span className="text-sm font-medium text-foreground">{t("Notifications (Enable)")}</span>
            </div>
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          </button>
          <button onClick={handleLanguageClick} className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Globe className="h-5 w-5 text-primary" />
              </div>
              <span className="text-sm font-medium text-foreground">{t("Change Language")}</span>
            </div>
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          </button>
          <button onClick={handleCurrencyClick} className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Wallet className="h-5 w-5 text-primary" />
              </div>
              <span className="text-sm font-medium text-foreground">{t("Base Currency")}</span>
            </div>
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          </button>
          <button onClick={handleHelpClick} className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <HelpCircle className="h-5 w-5 text-primary" />
              </div>
              <span className="text-sm font-medium text-foreground">{t("Help")}</span>
            </div>
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          </button>
        </Card>
      </div>
    </div>
  )
}
