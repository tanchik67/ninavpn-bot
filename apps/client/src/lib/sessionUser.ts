type Listener = (userId: string | null) => void;

let userId: string | null = null;
const listeners = new Set<Listener>();

export function getSessionUserId(): string | null {
  return userId;
}

export function setSessionUserId(id: string | null) {
  if (userId === id) return;
  userId = id;
  listeners.forEach((l) => l(id));
}

export function onSessionUserId(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
