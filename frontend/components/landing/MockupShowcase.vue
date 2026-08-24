<script setup lang="ts">
import { ref } from "vue";
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();

interface MockupItem {
  id: string;
  name: string;
  category: string;
  icon: string;
  aspect: string;
  blendMode: string;
  desc: string;
}

const mockups: MockupItem[] = [
  { id: "tshirt", name: "Graphic T-Shirt", category: "Apparel", icon: "lucide:shirt", aspect: "Classic Fit Unisex Tee", blendMode: "Solid / DTG Print", desc: "Realistic fabric folds, neckband alignment, and natural shading." },
  { id: "sweatshirt", name: "Cozy Sweatshirt", category: "Apparel", icon: "lucide:shirt", aspect: "Heavyweight Crewneck", blendMode: "Overlay / Textured", desc: "True textured fleece drape with centered chest placement." },
  { id: "mug", name: "Ceramic Mug", category: "Drinkware", icon: "lucide:coffee", aspect: "11oz / 15oz Gloss White", blendMode: "Sublimation Wrap", desc: "Cylindrical warp curve and realistic ceramic gloss highlight." },
  { id: "tumbler", name: "Skinny Tumbler", category: "Drinkware", icon: "lucide:cup-soda", aspect: "20oz Stainless Steel", blendMode: "Wrap Sublimation", desc: "Seamless vertical wrap with metallic rim reflections." },
  { id: "tote", name: "Canvas Tote Bag", category: "Bags", icon: "lucide:shopping-bag", aspect: "Heavy Cotton Canvas", blendMode: "Direct Print", desc: "Woven canvas texture and natural handle shadows." },
  { id: "poster", name: "Art Poster", category: "Wall Art", icon: "lucide:image", aspect: "Matte Fine Art Print", blendMode: "Full Color Raster", desc: "Crisp wall display with wooden frame and glass reflections." },
  { id: "sticker", name: "Die-Cut Sticker", category: "Stationery", icon: "lucide:tags", aspect: "Vinyl Waterproof Decal", blendMode: "Contour Die-Cut", desc: "Crisp white border cutout and peel-away angle preview." },
  { id: "phone", name: "Phone Case", category: "Accessories", icon: "lucide:smartphone", aspect: "Snap Case with Camera Gap", blendMode: "Edge-to-Edge", desc: "Precise camera cutout clearance and rounded bumper wraps." },
  { id: "candle", name: "Scented Candle", category: "Home Goods", icon: "lucide:flame", aspect: "9oz Amber Glass Jar", blendMode: "Kraft Label Wrap", desc: "Realistic glass reflections with textured adhesive label." },
];

const selectedMockup = ref<MockupItem>(mockups[0]);

function selectMockup(item: MockupItem) {
  selectedMockup.value = item;
}
</script>

<template>
  <section
    id="mockups"
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FAF9F5] dark:bg-[#0B0F17]"
    aria-labelledby="mockups-heading"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-600 dark:text-purple-400 text-xs font-semibold">
          <Icon name="lucide:shirt" class="size-3.5" aria-hidden="true" />
          Catalog Mockups
        </span>
        <h2
          id="mockups-heading"
          class="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100"
        >
          See your design on real products.
        </h2>
        <p class="text-sm sm:text-base lg:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          Place your master artwork automatically across 9 standard digital-creator product types with accurate perspective, realistic lighting, and natural fabric blend modes.
        </p>
      </div>

      <!-- Main Interactive Showcase Layout -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        
        <!-- Left: Product Selector Tabs (9 Catalog Products) -->
        <div class="lg:col-span-5 space-y-2 max-h-[480px] overflow-y-auto pr-1">
          <button
            v-for="item in mockups"
            :key="item.id"
            type="button"
            :class="[
              'w-full flex items-center justify-between p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer hover:-translate-y-0.5 active:translate-y-0',
              selectedMockup.id === item.id
                ? 'border-orange-500 bg-white dark:bg-stone-900 shadow-sm scale-[1.01]'
                : 'border-stone-200/80 dark:border-stone-800 bg-white/40 dark:bg-stone-900/40 hover:bg-white dark:hover:bg-stone-900 hover:border-orange-500/40',
            ]"
            @click="selectMockup(item)"
          >
            <div class="flex items-center gap-3 min-w-0">
              <div
                :class="[
                  'size-9 rounded-lg flex items-center justify-center shrink-0 transition-colors duration-200',
                  selectedMockup.id === item.id
                    ? 'bg-orange-600 text-white shadow-xs'
                    : 'bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300',
                ]"
              >
                <Icon :name="item.icon" class="size-4.5" aria-hidden="true" />
              </div>
              <div class="truncate">
                <p class="text-xs sm:text-sm font-bold text-stone-900 dark:text-stone-100 truncate">
                  {{ item.name }}
                </p>
                <span class="text-[11px] text-stone-500 dark:text-stone-400">
                  {{ item.aspect }}
                </span>
              </div>
            </div>

            <div class="text-right shrink-0">
              <span class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300">
                {{ item.category }}
              </span>
            </div>
          </button>
        </div>

        <!-- Right: Active Mockup Large Visual Canvas -->
        <div class="lg:col-span-7">
          <div class="rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-6 sm:p-8 shadow-xl relative overflow-hidden flex flex-col items-center justify-center min-h-[380px] sm:min-h-[440px]">
            
            <!-- Background Accent Blob -->
            <div class="absolute inset-0 bg-gradient-to-b from-stone-50/50 to-transparent dark:from-stone-950/40 pointer-events-none" />

            <!-- Dynamic Product Visual Mockup Container with Smooth Fade Transition -->
            <div class="relative z-10 w-full max-w-sm flex flex-col items-center text-center space-y-4 transition-all duration-300">
              
              <!-- Product Graphic Render Frame -->
              <div class="relative size-56 sm:size-64 rounded-2xl bg-stone-100 dark:bg-stone-800/80 border border-stone-200 dark:border-stone-700/80 flex items-center justify-center shadow-inner overflow-hidden hover:scale-[1.02] transition-transform duration-300">
                <!-- Base Silhouette Icon -->
                <Icon :name="selectedMockup.icon" class="size-36 text-stone-300 dark:text-stone-700/60" aria-hidden="true" />

                <!-- Placed Artwork Graphic Layer -->
                <div class="absolute inset-0 flex items-center justify-center p-8">
                  <div class="size-24 sm:size-28 rounded-full bg-gradient-to-tr from-amber-500 via-orange-500 to-rose-500 p-1 flex items-center justify-center shadow-md animate-pulse-soft">
                    <div class="size-full rounded-full bg-stone-950 flex items-center justify-center text-amber-400">
                      <Icon name="lucide:sparkles" class="size-10" />
                    </div>
                  </div>
                </div>

                <!-- Product Badge -->
                <div class="absolute top-2.5 right-2.5 bg-black/70 backdrop-blur-xs text-white text-[10px] font-bold px-2 py-0.5 rounded-md shadow-xs">
                  {{ selectedMockup.blendMode }}
                </div>
              </div>

              <!-- Product Info Description -->
              <div class="space-y-1">
                <h3 class="text-lg font-black text-stone-900 dark:text-stone-100">
                  {{ selectedMockup.name }}
                </h3>
                <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 max-w-xs">
                  {{ selectedMockup.desc }}
                </p>
              </div>

              <div class="flex items-center gap-2 pt-1 text-[11px] text-stone-500 dark:text-stone-400">
                <span class="size-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>Auto-centered with standard print bleed</span>
              </div>
            </div>

          </div>
        </div>

      </div>

    </div>
  </section>
</template>
