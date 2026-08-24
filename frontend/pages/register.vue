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

const auth = useAuthStore();
const router = useRouter();

const email = ref("");
const displayName = ref("");
const password = ref("");
const error = ref<string | null>(null);
const loading = ref(false);

async function handleRegister() {
  if (!email.value || !displayName.value || !password.value) {
    error.value = "All fields are required.";
    return;
  }
  if (password.value.length < 8) {
    error.value = "Password must be at least 8 characters long.";
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    await auth.register(email.value, displayName.value, password.value);
    router.push("/dashboard");
  } catch (err: unknown) {
    const errorData = err as { data?: { detail?: string } };
    if (errorData.data && errorData.data.detail) {
      error.value = errorData.data.detail;
    } else {
      error.value = "Registration failed. Please try again.";
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main
    id="main"
    class="min-h-screen bg-[#FAF9F5] dark:bg-[#0B0F17] flex items-center justify-center p-4 sm:p-6 text-stone-900 dark:text-stone-100"
  >
    <div class="w-full max-w-md">
      <div class="mb-8 text-center">
        <AppLogo sizeClass="size-12 mb-3 inline-block drop-shadow-md" />
        <h1 class="text-2xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100">
          NovaCraft<span class="text-orange-600 dark:text-orange-500">Pixel</span>
        </h1>
        <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">Autonomous research-to-draft digital product studio</p>
      </div>

      <Card class="shadow-xl border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 backdrop-blur-xs">
        <CardHeader class="space-y-1 pb-4">
          <CardTitle class="text-xl">Create your account</CardTitle>
          <CardDescription class="text-stone-500 dark:text-stone-400">Create your profile to get started</CardDescription>
        </CardHeader>

        <CardContent>
          <form class="space-y-4" @submit.prevent="handleRegister">
            <div class="space-y-1.5">
              <Label for="displayName">Display Name</Label>
              <div class="relative">
                <Input
                  id="displayName"
                  v-model="displayName"
                  type="text"
                  required
                  placeholder="Alex Rivers"
                  data-testid="register-name-input"
                  class="pl-9 focus-visible:ring-orange-500"
                />
                <Icon name="lucide:user" class="absolute left-3 top-2.5 size-4 text-stone-400 pointer-events-none" aria-hidden="true" />
              </div>
            </div>

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
                  data-testid="register-email-input"
                  class="pl-9 focus-visible:ring-orange-500"
                />
                <Icon name="lucide:mail" class="absolute left-3 top-2.5 size-4 text-stone-400 pointer-events-none" aria-hidden="true" />
              </div>
            </div>

            <div class="space-y-1.5">
              <Label for="password">Password (min 8 characters)</Label>
              <div class="relative">
                <Input
                  id="password"
                  v-model="password"
                  type="password"
                  required
                  autocomplete="new-password"
                  placeholder="••••••••"
                  data-testid="register-password-input"
                  class="pl-9 focus-visible:ring-orange-500"
                />
                <Icon name="lucide:lock" class="absolute left-3 top-2.5 size-4 text-stone-400 pointer-events-none" aria-hidden="true" />
              </div>
            </div>

            <Alert v-if="error" variant="destructive" data-testid="register-error">
              <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
              <AlertDescription>{{ error }}</AlertDescription>
            </Alert>

            <button
              type="submit"
              :disabled="loading"
              class="w-full font-bold shadow-md shadow-orange-600/20 bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white rounded-lg py-2.5 px-4 cursor-pointer inline-flex items-center justify-center gap-1 transition-all disabled:opacity-60"
              data-testid="register-submit-btn"
            >
              <span>{{ loading ? 'Creating Account...' : 'Sign Up' }}</span>
              <Icon v-if="!loading" name="lucide:arrow-right" class="size-4 ml-1" aria-hidden="true" />
            </button>
          </form>
        </CardContent>

        <CardFooter class="flex justify-center border-t border-stone-100 dark:border-stone-800 pt-4 text-xs text-stone-500 dark:text-stone-400">
          Already have an account?
          <NuxtLink to="/login" class="ml-1 font-semibold text-orange-600 hover:text-orange-700 dark:text-orange-400 dark:hover:text-orange-300 underline-offset-4 hover:underline">
            Sign In
          </NuxtLink>
        </CardFooter>
      </Card>
    </div>
  </main>
</template>
