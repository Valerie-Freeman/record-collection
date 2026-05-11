import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = "https://ytwrcffjmhkayzlfxctr.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0d3JjZmZqbWhrYXl6bGZ4Y3RyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc0MDU0MjgsImV4cCI6MjA5Mjk4MTQyOH0.SAEJUu7hJt1tYmVhgyHkqMXBiMmqDNUBcrfjZvC7nSQ";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
