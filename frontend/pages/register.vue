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
    router.push("/");
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
    class="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/20 to-slate-50 flex items-center justify-center p-4 sm:p-6"
  >
    <div class="w-full max-w-md">
      <div class="mb-8 text-center">
        <div class="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-white shadow-md shadow-blue-600/20 mb-3">
          <Icon name="lucide:store" class="size-6" aria-hidden="true" />
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-foreground">Marketplace Studio</h1>
        <p class="mt-1 text-sm text-muted-foreground">Autonomous research-to-draft digital product studio</p>
      </div>

      <Card class="shadow-xl border-border bg-card backdrop-blur-xs">
        <CardHeader class="space-y-1 pb-4">
          <CardTitle class="text-xl">Create your account</CardTitle>
          <CardDescription>Setup your owner profile to get started</CardDescription>
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
                  class="pl-9"
                />
                <Icon name="lucide:user" class="absolute left-3 top-2.5 size-4 text-muted-foreground pointer-events-none" aria-hidden="true" />
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
                  class="pl-9"
                />
                <Icon name="lucide:mail" class="absolute left-3 top-2.5 size-4 text-muted-foreground pointer-events-none" aria-hidden="true" />
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
                  class="pl-9"
                />
                <Icon name="lucide:lock" class="absolute left-3 top-2.5 size-4 text-muted-foreground pointer-events-none" aria-hidden="true" />
              </div>
            </div>

            <Alert v-if="error" variant="destructive" data-testid="register-error">
              <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
              <AlertDescription>{{ error }}</AlertDescription>
            </Alert>

            <Button
              type="submit"
              variant="default"
              size="lg"
              :loading="loading"
              class="w-full font-semibold shadow-md shadow-primary/20 cursor-pointer inline-flex items-center justify-center gap-1"
              data-testid="register-submit-btn"
            >
              <span>{{ loading ? 'Creating Account...' : 'Sign Up' }}</span>
              <Icon v-if="!loading" name="lucide:arrow-right" class="size-4 ml-1" aria-hidden="true" />
            </Button>
          </form>
        </CardContent>

        <CardFooter class="flex justify-center border-t border-border pt-4 text-xs text-muted-foreground">
          Already have an account?
          <NuxtLink to="/login" class="ml-1 font-semibold text-primary hover:text-primary-hover underline-offset-4 hover:underline">
            Sign In
          </NuxtLink>
        </CardFooter>
      </Card>
    </div>
  </main>
</template>
