"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { useTelegram } from "@/lib/telegram-provider"
import { completeTask, getUserData } from "@/lib/api"
import { 
  Flame, 
  Book, 
  Dumbbell, 
  Apple, 
  Moon,
  Droplet,
  Brain,
  CheckCircle,
  Target
} from "lucide-react"

interface Task {
  id: number
  title: string
  description?: string
  date: string
  is_completed: boolean
  is_ai: boolean
}

// Helper to assign random or pseudo-random visual properties to tasks
function getTaskVisuals(taskId: number, title: string) {
  const visuals = [
    { icon: Book, iconBg: "bg-blue-100", iconColor: "text-blue-600" },
    { icon: Dumbbell, iconBg: "bg-primary/10", iconColor: "text-primary" },
    { icon: Apple, iconBg: "bg-red-100", iconColor: "text-red-500" },
    { icon: Moon, iconBg: "bg-indigo-100", iconColor: "text-indigo-500" },
    { icon: Droplet, iconBg: "bg-cyan-100", iconColor: "text-cyan-500" },
    { icon: Brain, iconBg: "bg-purple-100", iconColor: "text-purple-500" },
    { icon: Target, iconBg: "bg-orange-100", iconColor: "text-orange-500" },
  ]
  const titleLow = title.toLowerCase()
  if (titleLow.includes("gym") || titleLow.includes("sport") || titleLow.includes("workout")) return visuals[1]
  if (titleLow.includes("book") || titleLow.includes("read") || titleLow.includes("kitob")) return visuals[0]
  if (titleLow.includes("water") || titleLow.includes("suv")) return visuals[4]
  if (titleLow.includes("sleep") || titleLow.includes("uxlash")) return visuals[3]
  if (titleLow.includes("eat") || titleLow.includes("ovqat") || titleLow.includes("diet")) return visuals[2]
  
  return visuals[taskId % visuals.length]
}

function getAiNudge(title: string, completed: boolean) {
  if (completed) return "Ajoyib natija! Barakalla. 🎉"
  return "Hali bajarilmadi. Maqsadingiz sari olg'a! 💡"
}

export function Discipline({ refreshTrigger = 0 }: { refreshTrigger?: number }) {
  const { user } = useTelegram()
  const [tasks, setTasks] = useState<Task[]>([])
  const [streak, setStreak] = useState(0)

  const loadTasks = async (userId: number) => {
    // We use getDashboardStats since it now bundles tasks and streak efficiently
    const { getDashboardStats } = await import("@/lib/api");
    const data = await getDashboardStats(userId)
    setTasks(data?.tasks || [])
    setStreak(data?.streak || 0)
  }

  useEffect(() => {
    if (!user?.id) return
    loadTasks(user.id)
  }, [user?.id, refreshTrigger])

  const toggleTask = async (task: Task) => {
    if (task.is_completed) return
    await completeTask(task.id)
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, is_completed: true } : t)))
  }

  const completedCount = tasks.filter(t => t.is_completed).length
  const totalCount = tasks.length
  const progressPercentage = totalCount ? (completedCount / totalCount) * 100 : 0

  return (
    <div className="p-5 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Daily Discipline</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Rejalaringizni bajarishni unutmang.
          </p>
        </div>
        
        {/* Streak Counter */}
        <div className="flex items-center gap-2 bg-gradient-to-br from-orange-400 to-red-500 px-4 py-2 rounded-2xl shadow-lg">
          <Flame className="h-5 w-5 text-white" />
          <span className="font-bold text-white">{streak}</span>
        </div>
      </div>

      {/* AI Motivation Card */}
      <Card className="p-4 bg-gradient-to-r from-primary/10 to-accent/30 border-0 rounded-3xl">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
            <span className="text-lg">🤖</span>
          </div>
          <div>
            <p className="font-medium text-foreground">Disciplix AI says:</p>
            <p className="text-sm text-muted-foreground mt-1">
              {"You've completed "}
              <span className="font-semibold text-primary">{completedCount}/{totalCount}</span>
              {" tasks today. "}
              {totalCount === 0 
                ? "Hali vazifa qo'shilmagan." 
                : completedCount < totalCount 
                  ? "Don't slack off now! You're almost there! 😤"
                  : "Amazing work! You're a discipline machine! 🔥"}
            </p>
          </div>
        </div>
      </Card>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-foreground">Today's Progress</span>
          <span className="text-sm font-semibold text-primary">{Math.round(progressPercentage)}%</span>
        </div>
        <div className="h-3 bg-muted rounded-full overflow-hidden">
          <div 
            className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-all duration-500"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      </div>

      {/* Task List */}
      <div className="space-y-3">
        <h2 className="font-semibold text-foreground">Bugungi vazifalar</h2>
        
        {tasks.length === 0 && (
          <Card className="p-4 bg-card border-0 rounded-2xl text-sm text-muted-foreground">
            Hozircha vazifalar yo'q.
          </Card>
        )}

        {tasks.map((task) => {
          const visual = getTaskVisuals(task.id, task.title)
          return (
            <Card 
              key={task.id} 
              className={`p-4 border-0 rounded-2xl shadow-sm transition-all duration-300 ${
                task.is_completed ? 'bg-primary/5' : 'bg-card'
              }`}
            >
              <div className="flex items-start gap-3">
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${visual.iconBg}`}>
                  <visual.icon className={`h-5 w-5 ${visual.iconColor}`} />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <div className="flex-1">
                      <p className={`font-medium ${task.is_completed ? 'line-through text-muted-foreground' : 'text-foreground'}`}>
                        {task.title}
                      </p>
                      {task.description && (
                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1 border-l-2 border-primary/20 pl-2">
                          {task.description}
                        </p>
                      )}
                      <p className="text-sm text-muted-foreground mt-1">{task.date || "Vaqt kiritilmagan"}</p>
                    </div>
                    <Checkbox 
                      checked={task.is_completed}
                      onCheckedChange={() => toggleTask(task)}
                      className="h-6 w-6 rounded-lg border-2 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                    />
                  </div>
                  
                  {/* AI Nudge */}
                  <div className={`mt-2 px-3 py-2 rounded-xl text-xs ${
                    task.is_completed 
                      ? 'bg-primary/10 text-primary' 
                      : 'bg-muted text-muted-foreground'
                  }`}>
                    <span className="mr-1">💡</span>
                    {getAiNudge(task.title, task.is_completed)}
                  </div>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
