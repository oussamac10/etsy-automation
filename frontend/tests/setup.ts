import { config } from "@vue/test-utils";

config.global.stubs = {
  Icon: {
    template: `<span class="icon-stub" :data-icon="$attrs.name"><slot /></span>`,
  },
};
