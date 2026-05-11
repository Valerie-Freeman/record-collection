import { supabase } from "./supabase.js";

const OWNERS = new Set(["valerah7@gmail.com", "caylonfreeman@gmail.com"]);

function ownerFromSession(session) {
  const email = session?.user?.email;
  return email && OWNERS.has(email) ? email : null;
}

export async function signInWithGoogle() {
  await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: `${location.origin}${location.pathname}` },
  });
}

export async function signOut() {
  await supabase.auth.signOut();
}

export async function getOwner() {
  const { data } = await supabase.auth.getSession();
  return ownerFromSession(data.session);
}

export function onOwnerChange(callback) {
  return supabase.auth.onAuthStateChange((_event, session) => {
    callback(ownerFromSession(session));
  });
}
