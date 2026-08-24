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
  dpi: string;
  bleed: string;
}

const mockups: MockupItem[] = [
  { id: "tshirt", name: "Graphic T-Shirt", category: "Apparel", icon: "lucide:shirt", aspect: "Classic Fit Unisex Tee", blendMode: "Solid / DTG Print", desc: "Realistic fabric folds, neckband alignment, and natural shading.", dpi: "300 DPI", bleed: "Centered DTG" },
  { id: "sweatshirt", name: "Cozy Sweatshirt", category: "Apparel", icon: "lucide:shirt", aspect: "Heavyweight Crewneck", blendMode: "Overlay / Textured", desc: "True textured fleece drape with centered chest placement.", dpi: "300 DPI", bleed: "Chest Centered" },
  { id: "mug", name: "Ceramic Mug", category: "Drinkware", icon: "lucide:coffee", aspect: "11oz / 15oz Gloss White", blendMode: "Sublimation Wrap", desc: "Cylindrical warp curve and realistic ceramic gloss highlight.", dpi: "300 DPI", bleed: "Full Sublimation" },
  { id: "tumbler", name: "Skinny Tumbler", category: "Drinkware", icon: "lucide:cup-soda", aspect: "20oz Stainless Steel", blendMode: "Wrap Sublimation", desc: "Seamless vertical wrap with metallic rim reflections.", dpi: "300 DPI", bleed: "Full Wrap" },
  { id: "tote", name: "Canvas Tote Bag", category: "Bags", icon: "lucide:shopping-bag", aspect: "Heavy Cotton Canvas", blendMode: "Direct Print", desc: "Woven canvas texture and natural handle shadows.", dpi: "300 DPI", bleed: "Flat Surface" },
  { id: "poster", name: "Art Poster", category: "Wall Art", icon: "lucide:image", aspect: "Matte Fine Art Print", blendMode: "Full Color Raster", desc: "Crisp wall display with wooden frame and glass reflections.", dpi: "300 DPI", bleed: "3:4 / 4:5 Ratio" },
  { id: "sticker", name: "Die-Cut Sticker", category: "Stationery", icon: "lucide:tags", aspect: "Vinyl Waterproof Decal", blendMode: "Contour Die-Cut", desc: "Crisp white border cutout and peel-away angle preview.", dpi: "300 DPI", bleed: "Contour Cut" },
  { id: "phone", name: "Phone Case", category: "Accessories", icon: "lucide:smartphone", aspect: "Snap Case with Camera Gap", blendMode: "Edge-to-Edge", desc: "Precise camera cutout clearance and rounded bumper wraps.", dpi: "300 DPI", bleed: "3D Wrap" },
  { id: "candle", name: "Scented Candle", category: "Home Goods", icon: "lucide:flame", aspect: "9oz Amber Glass Jar", blendMode: "Kraft Label Wrap", desc: "Realistic glass reflections with textured adhesive label.", dpi: "300 DPI", bleed: "Label Center" },
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
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FAF9F5] dark:bg-[#0B0F17] relative overflow-hidden scroll-mt-16 sm:scroll-mt-20 section-render-opt"
    aria-labelledby="mockups-heading"
  >
    <!-- Background Ambient Glow -->
    <div class="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden" aria-hidden="true">
      <div class="size-[500px] rounded-full bg-purple-500/5 dark:bg-purple-500/10 blur-3xl" />
    </div>

    <div class="relative mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-10 sm:space-y-12">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-600 dark:text-purple-400 text-xs font-semibold shadow-2xs">
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
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 sm:gap-8 items-center">
        
        <!-- Left: Product Selector Tabs (9 Catalog Products) -->
        <div class="lg:col-span-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-2">
          <button
            v-for="item in mockups"
            :key="item.id"
            type="button"
            :class="[
              'w-full flex items-center justify-between p-2.5 sm:p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer group',
              selectedMockup.id === item.id
                ? 'border-orange-500 bg-white dark:bg-stone-900 shadow-sm'
                : 'border-stone-200/80 dark:border-stone-800 bg-white/60 dark:bg-stone-900/40 hover:bg-white dark:hover:bg-stone-900 hover:border-orange-500/40',
            ]"
            @click="selectMockup(item)"
          >
            <div class="flex items-center gap-2.5 sm:gap-3 min-w-0">
              <div
                :class="[
                  'size-9 rounded-lg flex items-center justify-center shrink-0 transition-colors duration-200 shadow-2xs',
                  selectedMockup.id === item.id
                    ? 'bg-orange-600 text-white'
                    : 'bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 group-hover:bg-orange-500/10 group-hover:text-orange-600 dark:group-hover:text-orange-400',
                ]"
              >
                <Icon :name="item.icon" class="size-4.5" aria-hidden="true" />
              </div>
              <div class="truncate">
                <p class="text-xs sm:text-sm font-bold text-stone-900 dark:text-stone-100 truncate group-hover:text-orange-600 dark:group-hover:text-orange-400 transition-colors">
                  {{ item.name }}
                </p>
                <span class="text-[11px] text-stone-500 dark:text-stone-400">
                  {{ item.aspect }}
                </span>
              </div>
            </div>

            <div class="text-right shrink-0 flex items-center gap-1.5 sm:gap-2">
              <span class="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 border border-stone-200/60 dark:border-stone-700/60">
                {{ item.category }}
              </span>
              <Icon
                name="lucide:chevron-right"
                :class="[
                  'size-3.5 sm:size-4 transition-transform duration-200',
                  selectedMockup.id === item.id ? 'text-orange-600 translate-x-0.5' : 'text-stone-300 dark:text-stone-600 group-hover:text-stone-400',
                ]"
                aria-hidden="true"
              />
            </div>
          </button>
        </div>

        <!-- Right: Active Mockup Large Visual Canvas -->
        <div class="lg:col-span-7">
          <div class="rounded-3xl border border-stone-200/90 dark:border-stone-800 bg-white dark:bg-stone-900 p-6 sm:p-8 shadow-xl relative overflow-hidden flex flex-col items-center justify-center min-h-[420px] sm:min-h-[480px]">
            
            <!-- Studio Stage Top Header Bar -->
            <div class="w-full flex items-center justify-between border-b border-stone-100 dark:border-stone-800 pb-3 mb-6">
              <div class="flex items-center gap-2">
                <span class="size-2 rounded-full bg-emerald-500 animate-pulse" />
                <span class="text-xs font-bold text-stone-800 dark:text-stone-200">
                  Studio Compositor View
                </span>
              </div>
              <div class="flex items-center gap-2 text-[10px] font-semibold text-stone-500 dark:text-stone-400">
                <span class="px-2 py-0.5 rounded-md bg-stone-100 dark:bg-stone-800">
                  {{ selectedMockup.dpi }}
                </span>
                <span class="px-2 py-0.5 rounded-md bg-orange-500/10 text-orange-600 dark:text-orange-400 font-bold">
                  {{ selectedMockup.bleed }}
                </span>
              </div>
            </div>

            <!-- Dynamic Product Visual Mockup Container -->
            <div class="relative z-10 w-full max-w-sm flex flex-col items-center text-center space-y-5 transition-all duration-300">
              
              <!-- Product Graphic Render Frame -->
              <div class="relative size-60 sm:size-68 rounded-2xl bg-stone-100/90 dark:bg-stone-800/90 border border-stone-200 dark:border-stone-700/80 flex items-center justify-center shadow-inner overflow-hidden hover:scale-[1.02] transition-transform duration-300">
                <!-- Base Silhouette Icon -->
                <Icon :name="selectedMockup.icon" class="size-44 text-stone-400/90 dark:text-stone-500/70" aria-hidden="true" />

                <!-- Placed Artwork Graphic Layer (Transparent Master PNG on Product) -->
                <div class="absolute inset-0 flex items-center justify-center p-6 pointer-events-none">
                  <div class="flex flex-col items-center justify-center text-center filter drop-shadow-md transition-transform duration-300">
                    <div class="size-22 sm:size-26 rounded-2xl bg-gradient-to-tr from-amber-500/90 via-orange-500 to-rose-500 p-0.5 shadow-md flex items-center justify-center">
                      <div class="size-full rounded-2xl bg-stone-900/60 dark:bg-stone-950/70 backdrop-blur-xs flex flex-col items-center justify-center text-amber-400 p-2 border border-white/20">
                        <Icon name="lucide:sparkles" class="size-8 sm:size-9 text-amber-300 animate-spin-slow" />
                        <span class="text-[9px] font-black tracking-widest text-white uppercase mt-0.5">VINTAGE ART</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Product Badge -->
                <div class="absolute top-3 right-3 bg-stone-900/80 backdrop-blur-xs text-white text-[10px] font-extrabold px-2.5 py-1 rounded-lg shadow-md border border-white/10">
                  {{ selectedMockup.blendMode }}
                </div>
              </div>

              <!-- Product Info Description -->
              <div class="space-y-1.5">
                <h3 class="text-xl font-extrabold text-stone-900 dark:text-stone-100">
                  {{ selectedMockup.name }}
                </h3>
                <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 max-w-xs leading-relaxed">
                  {{ selectedMockup.desc }}
                </p>
              </div>

              <!-- Verification Check Footers -->
              <div class="flex flex-wrap items-center justify-center gap-3 pt-1 text-[11px] text-stone-500 dark:text-stone-400">
                <span class="inline-flex items-center gap-1">
                  <Icon name="lucide:check-circle" class="size-3.5 text-emerald-500" />
                  Auto-centered
                </span>
                <span class="inline-flex items-center gap-1">
                  <Icon name="lucide:check-circle" class="size-3.5 text-emerald-500" />
                  Natural Fabric Bleed
                </span>
                <span class="inline-flex items-center gap-1">
                  <Icon name="lucide:check-circle" class="size-3.5 text-emerald-500" />
                  Realistic Shading
                </span>
              </div>
            </div>

          </div>
        </div>

      </div>

    </div>
  </section>
</template>
