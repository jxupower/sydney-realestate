"use client";

import { useEffect, useState } from "react";

function generateId(): string {
  return crypto.randomUUID();
}

export function useSessionId(): string {
  const [sessionId, setSessionId] = useState<string>("");

  useEffect(() => {
    let id = localStorage.getItem("re-session-id");
    if (!id) {
      id = generateId();
      localStorage.setItem("re-session-id", id);
    }
    setSessionId(id);
  }, []);

  return sessionId;
}
