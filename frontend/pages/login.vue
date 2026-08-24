<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "~/stores/auth";
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
import AppLogo from "~/components/AppLogo.vue";
import LandingNavbar from "~/components/landing/LandingNavbar.vue";

const auth = useAuthStore();
const router = useRouter();

const email = ref("");
const password = ref("");
const showPassword = ref(false);
const error = ref<string | null>(null);
const loading = ref(false);

async function handleLogin() {
  const cleanEmail = email.value.trim().toLowerCase();
  const rawPassword = password.value;

  if (!cleanEmail || !rawPassword) {
    error.value = "Please enter both email and password.";
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    await auth.login(cleanEmail, rawPassword);
    router.push("/dashboard");
  } catch {
    error.value = "Invalid email or password.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen bg-[#FAF9F5] dark:bg-[#0B0F17] flex flex-col text-stone-900 dark:text-stone-100 selection:bg-orange-500/20 selection:text-orange-900 dark:selection:text-orange-200">
    <!-- Top Navigation Bar -->
    <LandingNavbar />

    <main
      id="main"
      class="flex-1 flex items-center justify-center p-4 sm:p-6"
    >
      <div class="w-full max-w-md py-6">
        <div class="mb-8 text-center">
          <AppLogo sizeClass="size-12 mb-3 inline-block drop-shadow-md" />
          <h1 class="text-2xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100">
            NovaCraft<span class="text-orange-600 dark:text-orange-500">Pixel</span>
          </h1>
          <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">Autonomous research-to-draft digital product studio</p>
        </div>

      <Card class="shadow-xl border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 backdrop-blur-xs">
        <CardHeader class="space-y-1 pb-4">
          <CardTitle class="text-xl">Sign in to your account</CardTitle>
          <CardDescription class="text-stone-500 dark:text-stone-400">Enter your credentials to manage campaigns and drafts</CardDescription>
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
                  autocapitalize="none"
                  autocorrect="off"
                  spellcheck="false"
                  placeholder="owner@example.com"
                  data-testid="login-email-input"
                  class="pl-9 focus-visible:ring-orange-500"
                />
                <Icon name="lucide:mail" class="absolute left-3 top-2.5 size-4 text-stone-400 pointer-events-none" aria-hidden="true" />
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
                  :type="showPassword ? 'text' : 'password'"
                  required
                  autocomplete="current-password"
                  autocapitalize="none"
                  autocorrect="off"
                  spellcheck="false"
                  placeholder="••••••••"
                  data-testid="login-password-input"
                  class="pl-9 pr-10 focus-visible:ring-orange-500"
                />
                <Icon name="lucide:lock" class="absolute left-3 top-2.5 size-4 text-stone-400 pointer-events-none" aria-hidden="true" />
                <button
                  type="button"
                  tabindex="-1"
                  class="absolute right-2.5 top-2.5 text-stone-400 hover:text-stone-600 dark:hover:text-stone-200 cursor-pointer focus:outline-none"
                  :aria-label="showPassword ? 'Hide password' : 'Show password'"
                  @click="showPassword = !showPassword"
                >
                  <Icon :name="showPassword ? 'lucide:eye-off' : 'lucide:eye'" class="size-4" aria-hidden="true" />
                </button>
              </div>
            </div>

            <Alert v-if="error" variant="destructive" data-testid="login-error">
              <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
              <AlertDescription>{{ error }}</AlertDescription>
            </Alert>

            <button
              type="submit"
              :disabled="loading"
              class="w-full font-bold shadow-md shadow-orange-600/20 bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white rounded-lg py-2.5 px-4 cursor-pointer inline-flex items-center justify-center gap-1 transition-all disabled:opacity-60"
              data-testid="login-submit-btn"
            >
              <span>{{ loading ? 'Signing in...' : 'Sign In' }}</span>
              <Icon v-if="!loading" name="lucide:arrow-right" class="size-4 ml-1" aria-hidden="true" />
            </button>
          </form>
        </CardContent>

        <CardFooter class="flex justify-center border-t border-stone-100 dark:border-stone-800 pt-4 text-xs text-stone-500 dark:text-stone-400">
          Don't have an account yet?
          <NuxtLink to="/register" class="ml-1 font-semibold text-orange-600 hover:text-orange-700 dark:text-orange-400 dark:hover:text-orange-300 underline-offset-4 hover:underline">
            Create account
          </NuxtLink>
        </CardFooter>
      </Card>
    </div>
  </main>
</div>
</template>
