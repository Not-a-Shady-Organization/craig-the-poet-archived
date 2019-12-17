import React from 'react';
import logo from './logo.svg';
import './App.css';
import Timeline from './Timeline.js';


let imageWidth = 100

function getWidth() {
  return Math.max(
    document.body.scrollWidth,
    document.documentElement.scrollWidth,
    document.body.offsetWidth,
    document.documentElement.offsetWidth,
    document.documentElement.clientWidth
  );
}


class App extends React.Component {

  constructor(props) {
    super(props)

    this.state = {
      totalTime: 20.,
      timelineWidth: getWidth() * .7,

      // These ones will update
      framePositions: {
        'grandma-image': {
          timePosition: 0,
          src: 'https://vetstreet-brightspot.s3.amazonaws.com/5b/24/619ffad0430b91abb7d8be71d69e/jessica-chastain-grandmas-dog-missing.jpg'
        },
        'dog-image': {
          timePosition: 18.,
          src: 'https://images.pexels.com/photos/1108099/pexels-photo-1108099.jpeg?auto=compress&cs=tinysrgb&dpr=1&w=500'
        }
      },
    }

    this.onDrag = this.onDrag.bind(this)
  }

  onDrag(elementID, position) {
    let framePositions = this.state.framePositions
    framePositions[elementID]['timePosition'] = position
    this.setState(framePositions)
  }

  callAPI() {
    fetch("http://127.0.0.1:5000/todo/api/v1.0/tasks")
    .then(response => response.json())
    .then(data => console.log(data))
  }


  render() {
    return (
      <div className="App">
        <Timeline
          timelineWidth={this.state.timelineWidth}
          imageWidth={imageWidth}

          totalTime={this.state.totalTime}
          frames={this.state.framePositions}
          onChange={this.onDrag}
        />

        <button
          onClick={() => this.callAPI()}
        >
          Generate
        </button>
      </div>
    );
  }
}

export default App;
