import { create } from 'zustand'
import { Socket } from 'socket.io-client'

export interface RemotePeer {
  id: string
  stream: MediaStream
  role: 'host' | 'guest' | 'observer'
  name: string
}

interface RoomState {
  role: 'host' | 'guest' | 'observer' | null
  userName: string
  isAuthenticated: boolean
  socket: Socket | null
  localStream: MediaStream | null
  remoteStreams: RemotePeer[]
  hostsCount: number
  videoEnabled: boolean
  audioEnabled: boolean
  aiStatus: string

  // Actions
  setAuth: (isAuthenticated: boolean, role: 'host' | 'guest' | 'observer' | null) => void
  setUserName: (name: string) => void
  setSocket: (socket: Socket | null) => void
  setLocalStream: (stream: MediaStream | null) => void
  addRemoteStream: (id: string, stream: MediaStream, role: 'host' | 'guest' | 'observer', name: string) => void
  removeRemoteStream: (id: string) => void
  setHostsCount: (count: number) => void
  toggleVideo: () => void
  toggleAudio: () => void
  setAiStatus: (status: string) => void
  resetStore: () => void
}

export const useRoomStore = create<RoomState>((set) => ({
  role: null,
  userName: '',
  isAuthenticated: false,
  socket: null,
  localStream: null,
  remoteStreams: [],
  hostsCount: 0,
  videoEnabled: true,
  audioEnabled: true,
  aiStatus: 'AI Offline',

  setAuth: (isAuthenticated, role) => set({ isAuthenticated, role }),
  setUserName: (userName) => set({ userName }),
  setSocket: (socket) => set({ socket }),
  setLocalStream: (localStream) => set({ localStream }),
  addRemoteStream: (id, stream, role, name) =>
    set((state) => {
      if (state.remoteStreams.some((peer) => peer.id === id)) {
        return state
      }
      return { remoteStreams: [...state.remoteStreams, { id, stream, role, name }] }
    }),
  removeRemoteStream: (id) =>
    set((state) => ({
      remoteStreams: state.remoteStreams.filter((peer) => peer.id !== id),
    })),
  setHostsCount: (hostsCount) => set({ hostsCount }),
  toggleVideo: () =>
    set((state) => {
      if (state.localStream) {
        const videoTrack = state.localStream.getVideoTracks()[0]
        if (videoTrack) {
          videoTrack.enabled = !videoTrack.enabled
        }
      }
      return { videoEnabled: !state.videoEnabled }
    }),
  toggleAudio: () =>
    set((state) => {
      if (state.localStream) {
        const audioTrack = state.localStream.getAudioTracks()[0]
        if (audioTrack) {
          audioTrack.enabled = !audioTrack.enabled
        }
      }
      return { audioEnabled: !state.audioEnabled }
    }),
  setAiStatus: (aiStatus) => set({ aiStatus }),
  resetStore: () =>
    set((state) => {
      if (state.localStream) {
        state.localStream.getTracks().forEach((track) => track.stop())
      }
      if (state.socket) {
        state.socket.disconnect()
      }
      return {
        role: null,
        userName: '',
        isAuthenticated: false,
        socket: null,
        localStream: null,
        remoteStreams: [],
        hostsCount: 0,
        videoEnabled: true,
        audioEnabled: true,
        aiStatus: 'AI Offline',
      }
    }),
}))
