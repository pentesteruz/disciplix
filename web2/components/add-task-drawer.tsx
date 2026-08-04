"use client"

import { useState } from "react"
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
} from "@/components/ui/drawer"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useTelegram } from "@/lib/telegram-provider"
import { addTask } from "@/lib/api"

interface AddTaskDrawerProps {
  isOpen: boolean
  onClose: () => void
  onTaskAdded: () => void
}

export function AddTaskDrawer({ isOpen, onClose, onTaskAdded }: AddTaskDrawerProps) {
  const { user } = useTelegram()
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [hour, setHour] = useState("")
  const [minute, setMinute] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState("")

  const handleSave = async () => {
    if (!title.trim() || !hour || !minute) {
      setError("Iltimos barcha maydonlarni to'ldiring")
      return
    }

    if (!user?.id) return

    setIsSaving(true)
    setError("")
    
    try {
      const now = new Date()
      const yyyy = now.getFullYear()
      const mm = String(now.getMonth() + 1).padStart(2, '0')
      const dd = String(now.getDate()).padStart(2, '0')
      const isoDateTime = `${yyyy}-${mm}-${dd}T${hour}:${minute}:00`

      await addTask(user.id, title.trim(), description.trim(), isoDateTime)
      setTitle("")
      setDescription("")
      setHour("")
      setMinute("")
      onTaskAdded()
      onClose()
    } catch (err: any) {
      setError(err?.message || "Vazifa qo'shishda xatolik yuz berdi")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Drawer open={isOpen} onOpenChange={onClose}>
      <DrawerContent>
        <div className="mx-auto w-full max-w-sm flex flex-col max-h-[85vh]">
          <DrawerHeader className="shrink-0">
            <DrawerTitle>Yangi vazifa</DrawerTitle>
            <DrawerDescription>
              Yangi vazifa nomi va uning muddatini (vaqtini) kiriting.
            </DrawerDescription>
          </DrawerHeader>
          
          <div className="p-4 pb-0 space-y-4 overflow-y-auto flex-1 scrollbar-none">
            {error && (
              <div className="text-sm font-medium text-destructive">{error}</div>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="task-title">Vazifa nomi</Label>
              <Input
                id="task-title"
                placeholder="Masalan: Kitob o'qish"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="task-desc">Vazifa tasnifi (ixtiyoriy)</Label>
              <Input
                id="task-desc"
                placeholder="Vazifa haqida batafsil ma'lumot"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="task-time">Bajarish vaqti</Label>
              <div className="flex gap-2 items-center">
                <select 
                  className="flex-1 bg-white h-12 rounded-[16px] border border-gray-100 shadow-[0_2px_12px_rgba(0,0,0,0.04)] px-4 focus:outline-none focus:ring-1 focus:ring-[#10B981] appearance-none"
                  value={hour}
                  onChange={(e) => setHour(e.target.value)}
                >
                  <option value="" disabled>Soat</option>
                  {Array.from({ length: 24 }).map((_, i) => {
                    const h = String(i).padStart(2, '0')
                    return <option key={h} value={h}>{h}</option>
                  })}
                </select>
                <span className="text-xl font-bold text-gray-400">:</span>
                <select 
                  className="flex-1 bg-white h-12 rounded-[16px] border border-gray-100 shadow-[0_2px_12px_rgba(0,0,0,0.04)] px-4 focus:outline-none focus:ring-1 focus:ring-[#10B981] appearance-none"
                  value={minute}
                  onChange={(e) => setMinute(e.target.value)}
                >
                  <option value="" disabled>Daqiqa</option>
                  {["00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55"].map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
          
          <DrawerFooter className="mt-2 shrink-0">
            <Button onClick={handleSave} disabled={isSaving || !title.trim() || !hour || !minute}>
              {isSaving ? "Saqlanmoqda..." : "Qo'shish"}
            </Button>
            <Button variant="outline" onClick={onClose} disabled={isSaving}>
              Bekor qilish
            </Button>
          </DrawerFooter>
        </div>
      </DrawerContent>
    </Drawer>
  )
}
