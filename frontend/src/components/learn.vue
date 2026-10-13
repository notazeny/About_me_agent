<script setup lang="ts">
// 声明这个组件接收一个 prop，名叫 list，类型是 string[]
defineProps<{ list: string[] }>()

// 声明会 emit 一个名叫 delete 的事件，带上一个 number 参数（下标）
const emit = defineEmits<{ (e: 'delete', index: number): void }>()
</script>

<template>
  <!-- v-for：遍历 list，每一条渲染成一个 <li> -->
  <!-- (item, i) = 元素值和下标；:key 给每条一个唯一标识（Vue 要求） -->
  <p v-if="list.length === 0">还没有留言</p>
  <ul v-else>
    <li v-for="(item, i) in list" :key="i">
    {{ item }}
    <button @click="emit('delete', i)">删除</button>
    </li>
  </ul>
</template>
