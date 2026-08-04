"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";

// Basic typings for the Telegram WebApp object
export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
  photo_url?: string;
}

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    query_id?: string;
    user?: TelegramUser;
    auth_date?: number;
    hash?: string;
  };
  version: string;
  platform: string;
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  headerColor: string;
  backgroundColor: string;
  expand: () => void;
  close: () => void;
  ready: () => void;
}

export interface TelegramContextType {
  webApp: TelegramWebApp | null;
  user: TelegramUser | null;
  isLoading: boolean;
}

const TelegramContext = createContext<TelegramContextType>({
  webApp: null,
  user: null,
  isLoading: true,
});

export function TelegramProvider({ children }: { children: ReactNode }) {
  const [webApp, setWebApp] = useState<TelegramWebApp | null>(null);
  const [user, setUser] = useState<TelegramUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    let retries = 0;
    const maxRetries = 50;

    const initTelegram = () => {
      if (typeof window !== "undefined" && (window as any).Telegram?.WebApp) {
        const tg = (window as any).Telegram.WebApp;
        
        // MUHIM: Eng birinchi ready() chaqirilishi kerak
        tg.ready();
        tg.expand();

        // Debug maqsadida loglar
        console.log("TG FULL OBJECT:", tg);
        console.log("TG INIT DATA:", tg.initData);
        console.log("TG UNSAFE DATA:", tg.initDataUnsafe);

        const userData = tg.initDataUnsafe?.user;

        if (isMounted) {
          setWebApp(tg);
          if (userData) {
             setUser(userData);
          } else if (process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_TEST_USER_ID) {
             setUser({
               id: Number(process.env.NEXT_PUBLIC_TEST_USER_ID),
               first_name: "Test",
               language_code: "uz"
             });
          } else {
             setUser(null);
          }
          setIsLoading(false);
        }
      } else {
        retries++;
        if (retries < maxRetries) {
          setTimeout(() => {
            if (isMounted) initTelegram();
          }, 100);
        } else if (isMounted) {
          console.warn("Telegram WebApp script not found after retries.");
          setIsLoading(false);
          setUser(null);
        }
      }
    };

    initTelegram();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <TelegramContext.Provider value={{ webApp, user, isLoading }}>
      {children}
    </TelegramContext.Provider>
  );
}

export function useTelegram() {
  return useContext(TelegramContext);
}
