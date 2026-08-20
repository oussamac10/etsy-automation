<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "~/stores/auth";
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
import AppLogo from "~/components/AppLogo.vue";

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
    class="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/20 to-slate-50 flex items-center justify-center p-4 sm:p-6"
  >
    <div class="w-full max-w-md">
      <div class="mb-8 text-center">
        <AppLogo sizeClass="size-12 mb-3 inline-block drop-shadow-md" />
        <h1 class="text-2xl font-bold tracking-tight text-foreground">Marketplace Studio</h1>
        <p class="mt-1 text-sm text-muted-foreground">Autonomous research-to-draft digital product studio</p>
      </div>

      <Card class="shadow-xl border-border bg-card backdrop-blur-xs">
        <CardHeader class="space-y-1 pb-4">
          <CardTitle class="text-xl">Sign in to your account</CardTitle>
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
                <Icon name="lucide:mail" class="absolute left-3 top-2.5 size-4 text-muted-foreground pointer-events-none" aria-hidden="true" />
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
                <Icon name="lucide:lock" class="absolute left-3 top-2.5 size-4 text-muted-foreground pointer-events-none" aria-hidden="true" />
              </div>
            </div>

            <Alert v-if="error" variant="destructive" data-testid="login-error">
              <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
              <AlertDescription>{{ error }}</AlertDescription>
            </Alert>

            <Button
              type="submit"
              variant="default"
              size="lg"
              :loading="loading"
              class="w-full font-semibold shadow-md shadow-primary/20 cursor-pointer inline-flex items-center justify-center gap-1"
              data-testid="login-submit-btn"
            >
              <span>{{ loading ? 'Signing in...' : 'Sign In' }}</span>
              <Icon v-if="!loading" name="lucide:arrow-right" class="size-4 ml-1" aria-hidden="true" />
            </Button>
          </form>
        </CardContent>

        <CardFooter class="flex justify-center border-t border-border pt-4 text-xs text-muted-foreground">
          Don't have an account yet?
          <NuxtLink to="/register" class="ml-1 font-semibold text-primary hover:text-primary-hover underline-offset-4 hover:underline">
            Create account
          </NuxtLink>
        </CardFooter>
      </Card>
    </div>
  </main>
</template>
