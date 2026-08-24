<script setup lang="ts">
const steps = [
  {
    step: "01",
    title: "Market Research",
    desc: "Scan real-time demand, buyer intent & seasonal timing signals.",
    icon: "lucide:search",
  },
  {
    step: "02",
    title: "Artwork Studio",
    desc: "Generate 300 DPI transparent PNGs with typography & variant support.",
    icon: "lucide:image",
  },
  {
    step: "03",
    title: "Realistic Mockups",
    desc: "Place artwork automatically across 9 standard creator items.",
    icon: "lucide:shirt",
  },
  {
    step: "04",
    title: "Listing SEO",
    desc: "Format high-ranking titles, descriptions, and 13 Etsy tags.",
    icon: "lucide:tags",
  },
  {
    step: "05",
    title: "Etsy Drafts",
    desc: "Export verified drafts straight to your Etsy store for manual publish.",
    icon: "lucide:store",
  },
];
</script>

<template>
  <section class="border-y border-stone-200/80 dark:border-stone-800 bg-[#FFFDF7]/60 dark:bg-stone-950/40 py-10 sm:py-14">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6 sm:gap-4 divide-y sm:divide-y-0 lg:divide-x divide-stone-200/70 dark:divide-stone-800">
        <div
          v-for="(item, index) in steps"
          :key="item.step"
          :class="[
            'flex flex-col space-y-2 pt-4 sm:pt-0',
            index > 0 ? 'lg:pl-6' : '',
          ]"
        >
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-extrabold text-orange-600 dark:text-orange-400 uppercase tracking-wider">
              Step {{ item.step }}
            </span>
            <div class="size-8 rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400 flex items-center justify-center">
              <Icon :name="item.icon" class="size-4" aria-hidden="true" />
            </div>
          </div>
          <h2 class="text-sm font-bold text-stone-900 dark:text-stone-100">
            {{ item.title }}
          </h2>
          <p class="text-xs text-stone-600 dark:text-stone-400 leading-relaxed">
            {{ item.desc }}
          </p>
        </div>
      </div>
    </div>
  </section>
</template>
