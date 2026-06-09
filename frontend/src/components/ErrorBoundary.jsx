// frontend/src/components/ErrorBoundary.jsx
import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-6 bg-red-50 border border-red-200 rounded-lg">
          <p className="font-semibold text-red-800">
            Something went wrong rendering this component.
          </p>
          <p className="text-xs text-red-600 mt-1 font-mono">
            {this.state.error.message}
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-3 text-xs text-red-700 underline">
            Dismiss
          </button>
        </div>
      )
    }
    return this.props.children
  }
}