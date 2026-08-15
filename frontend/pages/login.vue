<script setup lang="ts">
/* global useRouter */
import { ref } from "vue";
import { useAuthStore } from "~/stores/auth";
import { Sparkles, Mail, Lock, AlertCircle, ArrowRight } from "lucide-vue-next";
import Button from "~/components/ui/Button.vue";
import Input from "~/components/ui/Input.vue";
import Label from "~/components/ui/Label.vue";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import CardFooter from "~/components/ui/CardFooter.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";

const auth = useAuthStore();
const router = useRouter();

const email = ref("");
const password = ref("");
const error = ref<string | null>(null);
const loading = ref(false);

async function handleLogin() {
  if (!email.value || !password.value) {
    error.value = "Please enter both email and password.";
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    await auth.login(email.value, password.value);
    router.push("/");
  } catch {
    error.value = "Invalid email or password.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main
    id="main"
    class="min-h-screen bg-gradient-to-br from-slate-50 via-sky-50/30 to-indigo-50/20 flex items-center justify-center p-4 sm:p-6"
  >
    <div class="w-full max-w-md">
      <div class="mb-8 text-center">
        <div class="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-600 text-white shadow-md shadow-sky-600/20 mb-3">
          <Sparkles class="h-6 w-6" />
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900">Etsy Automation</h1>
        <p class="mt-1 text-sm text-slate-500">Autonomous research-to-draft PNG engine</p>
      </div>

      <Card class="shadow-xl border-slate-200/80 backdrop-blur-xs">
        <CardHeader class="space-y-1 pb-4">
          <CardTitle class="text-xl">Sign in to your shop</CardTitle>
          <CardDescription>Enter your credentials to manage campaigns and drafts</CardDescription>
        </CardHeader>

        <CardContent>
          <form class="space-y-4" @submit.prevent="handleLogin">
            <div class="space-y-1.5">
              <Label for="email">Email Address</Label>
              <div class="relative">
                <Input
                  id="email"
                  v-model="email"
                  type="email"
                  required
                  autocomplete="email"
                  placeholder="owner@example.com"
                  data-testid="login-email-input"
                  class="pl-9"
                />
                <Mail class="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
              </div>
            </div>

            <div class="space-y-1.5">
              <div class="flex items-center justify-between">
                <Label for="password">Password</Label>
              </div>
              <div class="relative">
                <Input
                  id="password"
                  v-model="password"
                  type="password"
                  required
                  autocomplete="current-password"
                  placeholder="••••••••"
                  data-testid="login-password-input"
                  class="pl-9"
                />
                <Lock class="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
              </div>
            </div>

            <Alert v-if="error" variant="destructive" data-testid="login-error">
              <AlertCircle class="h-4 w-4" />
              <AlertDescription>{{ error }}</AlertDescription>
            </Alert>

            <Button
              type="submit"
              variant="default"
              size="lg"
              :loading="loading"
              class="w-full font-semibold shadow-md shadow-sky-600/20"
              data-testid="login-submit-btn"
            >
              <span>{{ loading ? 'Signing in...' : 'Sign In' }}</span>
              <ArrowRight v-if="!loading" class="h-4 w-4 ml-1" />
            </Button>
          </form>
        </CardContent>

        <CardFooter class="flex justify-center border-t border-slate-100 pt-4 text-xs text-slate-500">
          Don't have an account yet?
          <NuxtLink to="/register" class="ml-1 font-semibold text-sky-600 hover:text-sky-700 underline-offset-4 hover:underline">
            Create account
          </NuxtLink>
        </CardFooter>
      </Card>
    </div>
  </main>
</template>
