import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import WorkflowConceptsTab from "~/components/workflow/WorkflowConceptsTab.vue";

const mockWorkflow = {
  id: "wf-123",
  state: "IDEA_REVIEW",
  version: 1,
  idea_mode: "market-led",
  target_country: "US",
};

const mockConcepts = [
  {
    id: "concept-1",
    workflow_id: "wf-123",
    original_idea_id: null,
    research_run_id: "run-1",
    title: "Retro Radiology Halloween Crew",
    description: "Hand-drawn retro kawaii skeleton and x-ray illustration designed for radiology tech Halloween shirts and mugs.",
    origin: "market",
    differentiation: "Combines proven healthcare Halloween seasonal demand with a highly specific radiology buyer group.",
    target_buyer: "Radiology Technologists & X-Ray Techs",
    buyer_use_case: "Healthcare / Radiology - Halloween",
    seasonality: "seasonal",
    risk_level: "low",
    risk_note: "Passed preliminary phrase screen.",
    score: 4.45,
    score_breakdown: {
      opportunity_type: "best_opportunity",
      overall_score: 89,
      scores: {
        overall: 89,
        demand: 92,
        competition_opportunity: 78,
        trend: 86,
        timing: 95,
        buyer_intent: 94,
        product_fit: 90,
      },
      competition: "Medium",
      trend_direction: "Rising",
      market_validation: "Strong",
      timing_label: "Prepare Now",
      recommended_launch_window: "August–October",
      why_it_could_sell: "Combines proven healthcare Halloween seasonal demand with a highly specific radiology buyer group.",
      keyword_cluster: ["radiology halloween png", "rad tech shirt design", "xray technician gift"],
      recommended_products: [
        { product: "tshirt", fit: 95 },
        { product: "mug", fit: 92 },
        { product: "sticker", fit: 88 },
      ],
      all_candidate_pool: [],
    },
    score_explanation: "High seasonal opportunity in healthcare.",
    status: "SHORTLISTED",
    created_at: "2026-08-21T18:00:00Z",
    prompts: [
      {
        id: "prompt-1",
        concept_id: "concept-1",
        version: 1,
        positive_prompt: "Retro 70s kawaii skeleton, isolated on transparent background, clean edges",
        negative_prompt: "background, scene, photo",
        typography_instructions: null,
        exact_slogan: null,
        intended_product_uses: ["tshirt", "mug"],
        style_notes: "Retro Groovy",
        palette: "#E07A5F, #3D405B",
        post_generation_checklist: ["transparent background"],
        change_note: "Initial prompt",
        created_at: "2026-08-21T18:00:00Z",
      },
    ],
  },
  {
    id: "concept-2",
    workflow_id: "wf-123",
    original_idea_id: null,
    research_run_id: "run-1",
    title: "Cozy Bookish Autumn Ghost",
    description: "Cute watercolor ghost reading books beside a pumpkin coffee.",
    origin: "market",
    differentiation: "Book lovers show high repeat purchase rates for cozy drinkware.",
    target_buyer: "Book Lovers, Librarians & Readers",
    buyer_use_case: "Bookish - Fall",
    seasonality: "seasonal",
    risk_level: "low",
    risk_note: "Passed preliminary phrase screen.",
    score: 4.30,
    score_breakdown: {
      opportunity_type: "niche_opportunity",
      overall_score: 86,
      scores: {
        overall: 86,
        demand: 90,
        competition_opportunity: 80,
        trend: 88,
        timing: 95,
        buyer_intent: 92,
        product_fit: 92,
      },
      competition: "Medium",
      trend_direction: "Rising",
      market_validation: "Strong",
      timing_label: "Prepare Now",
      recommended_launch_window: "August–October",
      why_it_could_sell: "High community engagement and gift-giving affinity for book lovers.",
      keyword_cluster: ["bookish ghost png", "reading fall sublimation"],
      recommended_products: [
        { product: "mug", fit: 96 },
        { product: "sweatshirt", fit: 94 },
      ],
      all_candidate_pool: [],
    },
    score_explanation: "Strong niche targeting.",
    status: "PROPOSED",
    created_at: "2026-08-21T18:00:00Z",
    prompts: [
      {
        id: "prompt-2",
        concept_id: "concept-2",
        version: 1,
        positive_prompt: "Cute ghost reading a book, watercolor, isolated transparent background",
        negative_prompt: "background, scene",
        typography_instructions: null,
        exact_slogan: null,
        intended_product_uses: ["mug", "sweatshirt"],
        style_notes: "Cozy Watercolor",
        palette: "#D4A373, #CCD5AE",
        post_generation_checklist: ["transparent background"],
        change_note: "Initial prompt",
        created_at: "2026-08-21T18:00:00Z",
      },
    ],
  },
  {
    id: "concept-3",
    workflow_id: "wf-123",
    original_idea_id: null,
    research_run_id: "run-1",
    title: "Cottagecore Botanical Frog Baker",
    description: "Vintage woodcut frog holding fresh sourdough bread.",
    origin: "market",
    differentiation: "Artisanal baking enthusiasts have high intent and low competition.",
    target_buyer: "Bakers & Cottagecore Crafters",
    buyer_use_case: "Baking - Evergreen",
    seasonality: "evergreen",
    risk_level: "low",
    risk_note: "Passed preliminary phrase screen.",
    score: 4.15,
    score_breakdown: {
      opportunity_type: "emerging_opportunity",
      overall_score: 83,
      scores: {
        overall: 83,
        demand: 82,
        competition_opportunity: 88,
        trend: 84,
        timing: 85,
        buyer_intent: 90,
        product_fit: 88,
      },
      competition: "Low",
      trend_direction: "Rising",
      market_validation: "Moderate",
      timing_label: "Evergreen",
      recommended_launch_window: "Year-Round",
      why_it_could_sell: "Unique subculture intersection with low market saturation.",
      keyword_cluster: ["frog baker png", "sourdough bread shirt"],
      recommended_products: [
        { product: "tote", fit: 94 },
        { product: "sticker", fit: 92 },
      ],
      all_candidate_pool: [],
    },
    score_explanation: "Emerging subculture trend.",
    status: "PROPOSED",
    created_at: "2026-08-21T18:00:00Z",
    prompts: [
      {
        id: "prompt-3",
        concept_id: "concept-3",
        version: 1,
        positive_prompt: "Vintage frog baker holding sourdough, isolated transparent background",
        negative_prompt: "background, scene",
        typography_instructions: null,
        exact_slogan: null,
        intended_product_uses: ["tote", "sticker"],
        style_notes: "Vintage Woodcut",
        palette: "#606C38, #283618",
        post_generation_checklist: ["transparent background"],
        change_note: "Initial prompt",
        created_at: "2026-08-21T18:00:00Z",
      },
    ],
  },
];

describe("WorkflowConceptsTab - Market Opportunity Discovery", () => {
  it("renders 3 opportunity cards with respective archetype badges", () => {
    const wrapper = mount(WorkflowConceptsTab, {
      props: {
        workflow: mockWorkflow,
        concepts: mockConcepts as any,
        latestRun: null,
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
          Button: { template: "<button><slot /></button>" },
          Badge: { template: "<span class='badge'><slot /></span>" },
          Card: { template: "<div class='card'><slot /></div>" },
          CardHeader: { template: "<div class='card-header'><slot /></div>" },
          CardTitle: { template: "<h3 class='card-title'><slot /></h3>" },
          CardContent: { template: "<div class='card-content'><slot /></div>" },
          CardFooter: { template: "<div class='card-footer'><slot /></div>" },
          Alert: { template: "<div><slot /></div>" },
          AlertTitle: { template: "<div><slot /></div>" },
          AlertDescription: { template: "<div><slot /></div>" },
          Dialog: { template: "<div><slot /></div>" },
          DialogHeader: { template: "<div><slot /></div>" },
          DialogTitle: { template: "<div><slot /></div>" },
          DialogDescription: { template: "<div><slot /></div>" },
          DialogFooter: { template: "<div><slot /></div>" },
        },
      },
    });

    const text = wrapper.text();
    expect(text).toContain("BEST OPPORTUNITY");
    expect(text).toContain("NICHE OPPORTUNITY");
    expect(text).toContain("EMERGING OPPORTUNITY");
    expect(text).toContain("Retro Radiology Halloween Crew");
    expect(text).toContain("89/100");
    expect(text).toContain("86/100");
    expect(text).toContain("83/100");
    expect(text).toContain("Why This Could Sell");
    expect(text).toContain("Use This Idea");
    expect(text).toContain("See Research");
    expect(text).toContain("Refresh Idea");
  });

  it("emits decideGate event when 'Use This Idea' is clicked", async () => {
    const wrapper = mount(WorkflowConceptsTab, {
      props: {
        workflow: mockWorkflow,
        concepts: mockConcepts as any,
        latestRun: null,
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
          Button: {
            template: "<button @click=\"$emit('click')\"><slot /></button>",
          },
          Badge: { template: "<span><slot /></span>" },
          Card: { template: "<div><slot /></div>" },
          CardHeader: { template: "<div><slot /></div>" },
          CardTitle: { template: "<h3><slot /></h3>" },
          CardContent: { template: "<div><slot /></div>" },
          CardFooter: { template: "<div><slot /></div>" },
          Alert: { template: "<div><slot /></div>" },
          AlertTitle: { template: "<div><slot /></div>" },
          AlertDescription: { template: "<div><slot /></div>" },
          Dialog: { template: "<div><slot /></div>" },
          DialogHeader: { template: "<div><slot /></div>" },
          DialogTitle: { template: "<div><slot /></div>" },
          DialogDescription: { template: "<div><slot /></div>" },
          DialogFooter: { template: "<div><slot /></div>" },
        },
      },
    });

    // Find all 'Use This Idea' buttons
    const buttons = wrapper.findAll("button");
    const useIdeaBtn = buttons.find((b) => b.text().includes("Use This Idea"));
    expect(useIdeaBtn).toBeDefined();

    await useIdeaBtn?.trigger("click");
    expect(wrapper.emitted("decideGate")).toBeTruthy();
    expect(wrapper.emitted("decideGate")?.[0]).toEqual(["concept-1", "APPROVED"]);
  });

  it("emits startResearch when 'Find New Ideas' is clicked", async () => {
    const wrapper = mount(WorkflowConceptsTab, {
      props: {
        workflow: mockWorkflow,
        concepts: mockConcepts as any,
        latestRun: null,
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
          Button: {
            template: "<button @click=\"$emit('click')\"><slot /></button>",
          },
          Badge: { template: "<span><slot /></span>" },
          Card: { template: "<div><slot /></div>" },
          CardHeader: { template: "<div><slot /></div>" },
          CardTitle: { template: "<h3><slot /></h3>" },
          CardContent: { template: "<div><slot /></div>" },
          CardFooter: { template: "<div><slot /></div>" },
          Alert: { template: "<div><slot /></div>" },
          AlertTitle: { template: "<div><slot /></div>" },
          AlertDescription: { template: "<div><slot /></div>" },
          Dialog: { template: "<div><slot /></div>" },
          DialogHeader: { template: "<div><slot /></div>" },
          DialogTitle: { template: "<div><slot /></div>" },
          DialogDescription: { template: "<div><slot /></div>" },
          DialogFooter: { template: "<div><slot /></div>" },
        },
      },
    });

    const findNewBtn = wrapper.find('[data-testid="regenerate-ideas-btn"]');
    expect(findNewBtn.exists()).toBe(true);

    await findNewBtn.trigger("click");
    expect(wrapper.emitted("startResearch")).toBeTruthy();
  });
});
